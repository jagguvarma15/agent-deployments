"""Concrete tool implementations for the restaurant-rebooking overlay.

Three adapters cover the domain primitives an LLM scaffolding this
recipe needs to see:

  - ``resy_adapter.search_slots`` / ``opentable_adapter.search_slots``
    return ``Slot`` lists. Mocked here against an in-memory inventory;
    the real adapters would call the respective platforms' REST APIs.
  - ``policy_lookup.is_eligible`` returns an ``EligibilityDecision``.
    Mocked against a tier table; the real lookup would hit the customer
    profile service.
  - ``notifier.send_sms`` takes a ``NotificationDraft`` and pretends to
    deliver it. Mocked; the real sender would call Twilio / MessageBird.

Real projects swap the function bodies; the call signatures and return
types stay the same. That's the contract the recipe pins.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Protocol

from .schemas import (
    EligibilityDecision,
    NotificationDraft,
    Party,
    Reservation,
    Slot,
    Tier,
)

log = logging.getLogger(__name__)

# ── Mock inventory (would come from the platform's API) ───────────────────────

_MOCK_RESY_SLOTS: list[Slot] = [
    Slot(
        venue_id="venue_42",
        starts_at=datetime.fromisoformat("2026-06-05T19:00:00+00:00"),
        duration_minutes=90,
        capacity_for_party=4,
        source="resy",
    ),
    Slot(
        venue_id="venue_42",
        starts_at=datetime.fromisoformat("2026-06-05T20:30:00+00:00"),
        duration_minutes=90,
        capacity_for_party=6,
        source="resy",
    ),
]

_MOCK_OPENTABLE_SLOTS: list[Slot] = [
    Slot(
        venue_id="venue_42",
        starts_at=datetime.fromisoformat("2026-06-05T19:15:00+00:00"),
        duration_minutes=120,
        capacity_for_party=4,
        source="opentable",
    ),
]


# ── Resy adapter ──────────────────────────────────────────────────────────────


class _HttpClient(Protocol):
    """Minimal contract the real adapter would depend on. Tests pass a fake."""

    def get(self, url: str, params: dict[str, str | int]) -> dict: ...


class ResyAdapter:
    """Wraps the Resy availability endpoint.

    Real call shape (production):
        GET https://api.resy.com/3/venues/{venue_id}/availability
              ?party_size={n}&start={iso}&end={iso}
        Headers: Authorization: ResyAPI api_key="..."
        Response: {"slots": [{"start": ..., "duration": ..., "max_party": ...}, ...]}

    The mock body returns ``_MOCK_RESY_SLOTS`` filtered by party size so
    the demo end-to-end produces a non-empty result.
    """

    def __init__(self, http: _HttpClient | None = None) -> None:
        self._http = http

    def search_slots(self, reservation: Reservation, *, window_hours: int = 4) -> list[Slot]:
        """Return alternative slots near ``reservation.starts_at`` for the same party size."""
        lower = reservation.starts_at - timedelta(hours=window_hours)
        upper = reservation.starts_at + timedelta(hours=window_hours)
        slots = [
            slot
            for slot in _MOCK_RESY_SLOTS
            if slot.venue_id == reservation.venue_id
            and lower <= slot.starts_at <= upper
            and slot.capacity_for_party >= reservation.party_size
        ]
        log.info("resy.search_slots resv=%s -> %d slots", reservation.reservation_id, len(slots))
        return slots


# ── OpenTable adapter ─────────────────────────────────────────────────────────


class OpenTableAdapter:
    """Wraps the OpenTable Affiliate API.

    Real call shape:
        GET https://platform.otrest.com/v1/restaurants/{venue_id}/availability
            ?datetime={iso}&partySize={n}
        Headers: Authorization: Bearer ...
        Response: {"availability": [{"slot": ..., "duration_minutes": ...}, ...]}
    """

    def __init__(self, http: _HttpClient | None = None) -> None:
        self._http = http

    def search_slots(self, reservation: Reservation, *, window_hours: int = 4) -> list[Slot]:
        lower = reservation.starts_at - timedelta(hours=window_hours)
        upper = reservation.starts_at + timedelta(hours=window_hours)
        slots = [
            slot
            for slot in _MOCK_OPENTABLE_SLOTS
            if slot.venue_id == reservation.venue_id
            and lower <= slot.starts_at <= upper
            and slot.capacity_for_party >= reservation.party_size
        ]
        log.info("opentable.search_slots resv=%s -> %d slots", reservation.reservation_id, len(slots))
        return slots


# ── Policy lookup ─────────────────────────────────────────────────────────────


_TIER_RANK: dict[Tier, int] = {
    Tier.standard: 0,
    Tier.silver: 1,
    Tier.gold: 2,
    Tier.platinum: 3,
}


def policy_is_eligible(party: Party, reservation: Reservation) -> EligibilityDecision:
    """Mock eligibility check.

    Real version would look up the customer profile + venue policy, e.g.::

        GET /profiles/{customer_id}/eligibility?venue_id={...}
        Response: {"eligible": bool, "reasons": [...], "requires_manager": bool}
    """
    if party.tier == Tier.standard and reservation.party_size > 4:
        return EligibilityDecision(
            eligible=False,
            reason_code="tier_too_low",
            rationale="Standard tier limited to parties of 4 for instant rebooking.",
            requires_manager_approval=True,
        )
    if _TIER_RANK[party.tier] >= _TIER_RANK[Tier.gold]:
        return EligibilityDecision(
            eligible=True,
            reason_code="eligible",
            rationale=f"{party.tier.value.title()} tier — instant rebooking allowed.",
        )
    return EligibilityDecision(
        eligible=True,
        reason_code="eligible",
        rationale="Within standard-tier party-size limits.",
    )


# ── Notifier ──────────────────────────────────────────────────────────────────


class NotifierResult(dict):
    """Lightweight return type — keeps the contract obvious in the walkthrough."""


def notifier_send_sms(party: Party, draft: NotificationDraft) -> NotifierResult:
    """Mock SMS send.

    Real version (Twilio):
        POST https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json
        Form: To, From, Body, MessagingServiceSid
        Response: {"sid": "SM...", "status": "queued"}
    """
    if not party.sms_opt_in:
        log.info("notifier.send_sms skipped (opt-out): %s", party.customer_id)
        return NotifierResult({"delivered": False, "reason": "sms_opt_out"})
    log.info(
        "notifier.send_sms customer=%s body=%r",
        party.customer_id,
        draft.body[:60],
    )
    return NotifierResult({"delivered": True, "channel": draft.channel})
