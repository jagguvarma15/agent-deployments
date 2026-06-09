"""End-to-end walkthrough wiring for the restaurant-rebooking overlay.

Composes the schemas, tools, and prompts into a single ``handle_event``
entry point that takes a raw ``CancellationEvent`` payload and returns a
``RebookingOutcome``. The pipeline is deterministic where possible
(eligibility + slot search) and only delegates the final notification
body to an LLM — but the model call is stubbed so the walkthrough runs
without an API key. Real projects swap ``_draft_notification`` for a
real ``anthropic`` call.

Pattern this composes: Event-Driven (consume → enrich → decide → act →
emit). See ``../../overview.md`` and the recipe at
``agent-deployments/docs/recipes/restaurant-rebooking.md``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from .schemas import (
    EligibilityDecision,
    NotificationDraft,
    Party,
    RebookingOutcome,
    Reservation,
    Slot,
    SlotRanking,
    Tier,
)
from .tools import (
    OpenTableAdapter,
    ResyAdapter,
    notifier_send_sms,
    policy_is_eligible,
)

log = logging.getLogger(__name__)

# ── Mock customer lookup ──────────────────────────────────────────────────────

_MOCK_PARTIES: dict[str, Party] = {
    "cust_7": Party(customer_id="cust_7", name="Ada Lovelace", tier=Tier.platinum),
    "cust_11": Party(customer_id="cust_11", name="Grace Hopper", tier=Tier.gold),
    "cust_13": Party(
        customer_id="cust_13",
        name="Alan Turing",
        tier=Tier.standard,
        sms_opt_in=False,
    ),
}


def lookup_party(customer_id: str) -> Party | None:
    return _MOCK_PARTIES.get(customer_id)


# ── Step: enrich ─────────────────────────────────────────────────────────────


def enrich(payload: dict) -> tuple[Party | None, Reservation]:
    """Lift the event payload into typed Party + Reservation. Mirrors the
    ``intake`` role's contract (see ``prompts.INTAKE_SYSTEM_PROMPT``)."""
    reservation = Reservation(
        reservation_id=payload["reservation_id"],
        venue_id=payload["venue_id"],
        customer_id=payload["customer_id"],
        party_size=int(payload["party_size"]),
        starts_at=datetime.fromisoformat(payload["starts_at"]),
        source=payload.get("source", "unknown"),
    )
    party = lookup_party(payload["customer_id"])
    return party, reservation


# ── Step: decide ─────────────────────────────────────────────────────────────


def rank_slots(reservation: Reservation, resy: ResyAdapter, ot: OpenTableAdapter) -> SlotRanking:
    """Pull from both adapters and rank per ``prompts.SEARCH_SYSTEM_PROMPT``."""
    candidates: list[Slot] = []
    candidates.extend(resy.search_slots(reservation))
    candidates.extend(ot.search_slots(reservation))

    if not candidates:
        return SlotRanking(slots=[], ranking_rationale="No alternative slots within window.")

    def _delta(slot: Slot) -> tuple[float, int, int]:
        time_delta = abs((slot.starts_at - reservation.starts_at).total_seconds())
        same_source_bonus = 0 if slot.source == reservation.source else 1
        return (time_delta, same_source_bonus, slot.capacity_for_party)

    ranked = sorted(candidates, key=_delta)
    return SlotRanking(
        slots=ranked,
        ranking_rationale=(
            f"Sorted by time delta to original ({reservation.starts_at.isoformat()}); {ranked[0].source} won."
        ),
    )


# ── Step: notify (stubbed LLM) ────────────────────────────────────────────────


def _draft_notification(
    party: Party, reservation: Reservation, outcome_action: str, slot: Slot | None
) -> NotificationDraft:
    """Stand-in for the ``notifier`` role's structured-output LLM call.

    Real production code calls ``anthropic.Anthropic().messages.create(...)``
    with ``prompts.NOTIFIER_SYSTEM_PROMPT`` as system + the
    Party/Reservation/Outcome/Slot JSON as input, and parses a
    ``NotificationDraft`` from the response. The stub here keeps the
    walkthrough offline-cheap.
    """
    channel = "sms" if party.sms_opt_in else "email"
    requires_translation = party.locale not in {"en-US", "en-GB"}
    if outcome_action == "rebooked" and slot is not None:
        body = (
            f"Hi {party.name}, your reservation at {slot.venue_id} was cancelled. "
            f"We've rebooked you for {slot.starts_at.isoformat()} (was "
            f"{reservation.starts_at.isoformat()}). Sorry for the shuffle."
        )
    elif outcome_action == "notify_host_only":
        body = (
            f"Host: cancellation for {reservation.reservation_id} requires manager "
            "approval before we offer a rebooking."
        )
    else:
        body = (
            f"Hi {party.name}, we couldn't find an alternative slot for your "
            f"{reservation.reservation_id} booking. Please pick a new time at "
            "the link below."
        )
    return NotificationDraft(channel=channel, body=body, requires_translation=requires_translation)


# ── Step: act ─────────────────────────────────────────────────────────────────


def handle_event(payload: dict) -> RebookingOutcome:
    """The full enrich → decide → act → notify chain.

    Returns a typed ``RebookingOutcome``; callers persist it + emit any
    follow-up events. The walkthrough's test asserts on this return.
    """
    party, reservation = enrich(payload)
    if party is None:
        return RebookingOutcome(
            action="dlq",
            rationale=f"Unknown customer_id {payload['customer_id']!r}; routed to DLQ.",
        )

    decision: EligibilityDecision = policy_is_eligible(party, reservation)
    if not decision.eligible:
        draft = _draft_notification(party, reservation, "notify_host_only", None)
        notifier_send_sms(party, draft)
        return RebookingOutcome(
            action="notify_host_only",
            notification_sent=True,
            rationale=decision.rationale,
        )

    ranking = rank_slots(reservation, ResyAdapter(), OpenTableAdapter())
    best = ranking.best
    if best is None:
        draft = _draft_notification(party, reservation, "declined", None)
        notifier_send_sms(party, draft)
        return RebookingOutcome(
            action="declined",
            notification_sent=True,
            rationale=ranking.ranking_rationale,
        )

    new_reservation_id = f"rsv_new_{party.customer_id}"
    draft = _draft_notification(party, reservation, "rebooked", best)
    delivery = notifier_send_sms(party, draft)
    return RebookingOutcome(
        action="rebooked",
        new_reservation_id=new_reservation_id,
        notification_sent=bool(delivery.get("delivered")),
        rationale=f"Rebooked to {best.source} slot at {best.starts_at.isoformat()}.",
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Three example payloads matching the doc's "Concrete data" section.
    examples = [
        {
            "reservation_id": "rsv_123",
            "venue_id": "venue_42",
            "customer_id": "cust_7",
            "party_size": 4,
            "starts_at": "2026-06-05T19:00:00+00:00",
            "source": "resy",
        },
        {
            "reservation_id": "rsv_124",
            "venue_id": "venue_42",
            "customer_id": "cust_13",
            "party_size": 6,
            "starts_at": "2026-06-05T19:00:00+00:00",
            "source": "resy",
        },
        {
            "reservation_id": "rsv_125",
            "venue_id": "venue_999",
            "customer_id": "cust_11",
            "party_size": 2,
            "starts_at": "2026-06-05T19:00:00+00:00",
            "source": "opentable",
        },
    ]
    for payload in examples:
        outcome = handle_event(payload)
        print(f"{payload['reservation_id']:10s} -> {outcome.action:18s} | {outcome.rationale}")
    print(f"Run at {datetime.now(UTC).isoformat()}")
