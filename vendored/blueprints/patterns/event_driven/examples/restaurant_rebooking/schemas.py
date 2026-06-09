"""Domain schemas for the restaurant-rebooking event-driven overlay.

Composes with the canonical Event-Driven state in
``patterns/event_driven/schemas/state.py`` (see :class:`Case`,
:class:`Event`) and adds the restaurant-domain types this overlay needs:
``Party``, ``Reservation``, ``Slot``, the agent's per-step decisions
(``EligibilityDecision``, ``SlotRanking``, ``NotificationDraft``), and the
terminal :class:`RebookingOutcome` the actor emits — which references the
canonical :class:`Case` so the overlay outcome can be traced back to the
event that drove it.

All Pydantic v2. Field descriptions are user-visible to the LLM via the
JSON Schemas generated for tool / structured-output calls.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from patterns.event_driven.schemas.state import Case, Event  # noqa: F401


class Tier(str, Enum):
    """Customer tier — affects eligibility for VIP-only logic."""

    standard = "standard"
    silver = "silver"
    gold = "gold"
    platinum = "platinum"


class Party(BaseModel):
    """A diner whose reservation was cancelled."""

    model_config = ConfigDict(frozen=True)

    customer_id: str
    name: str
    tier: Tier = Tier.standard
    locale: str = Field(default="en-US", description="BCP-47 language tag.")
    sms_opt_in: bool = True


class Reservation(BaseModel):
    """The original reservation that was cancelled."""

    reservation_id: str
    venue_id: str
    customer_id: str
    party_size: int = Field(ge=1, le=20)
    starts_at: datetime
    source: str = Field(description="Booking platform that owns the reservation.")


class Slot(BaseModel):
    """One alternative slot returned by a booking-platform adapter."""

    venue_id: str
    starts_at: datetime
    duration_minutes: int = 90
    capacity_for_party: int = Field(
        description="Max party size the slot can host without splitting.",
    )
    source: str = Field(description="Adapter that owns the slot (e.g. 'resy', 'opentable').")


class EligibilityDecision(BaseModel):
    """The eligibility role's structured output."""

    eligible: bool
    reason_code: str = Field(
        description="Machine-readable reason — `tier_too_low` / `policy_violation` / `eligible`.",
    )
    rationale: str = Field(description="One-line human-readable explanation.")
    requires_manager_approval: bool = False


class SlotRanking(BaseModel):
    """The search role's structured output: ranked slots with scores."""

    slots: list[Slot]
    ranking_rationale: str = Field(
        description="One sentence on why these slots are in this order.",
    )

    @property
    def best(self) -> Slot | None:
        return self.slots[0] if self.slots else None


class NotificationDraft(BaseModel):
    """The notifier role's structured output before send."""

    channel: str = Field(default="sms", description="`sms` / `email` / `push`.")
    body: str
    requires_translation: bool = False


class RebookingOutcome(BaseModel):
    """Terminal outcome the actor persists + emits.

    Carries the originating canonical :class:`Case` so downstream
    consumers (audit log, replay, DLQ tooling) can link this overlay-
    specific outcome back to the event-driven contract without re-
    parsing the original event payload.
    """

    case: Case | None = Field(
        default=None,
        description="The enriched Case this outcome was produced from.",
    )
    action: str = Field(
        description=(
            "`rebooked` / `notify_host_only` / `declined` / `dlq` — the actor's "
            "machine-readable verb for what happened."
        ),
    )
    new_reservation_id: str | None = None
    notification_sent: bool = False
    rationale: str = Field(description="One sentence on the final decision path.")
