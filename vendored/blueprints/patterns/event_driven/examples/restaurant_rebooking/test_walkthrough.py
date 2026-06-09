"""End-to-end walkthrough tests for the restaurant-rebooking overlay.

Runs without an API key — the notifier's draft step is deterministic in
``main._draft_notification`` so the chain is fully exercisable offline.

Run:
    uv run --with pydantic --with pytest python -m pytest test_walkthrough.py -v

Or as a script:
    uv run --with pydantic python test_walkthrough.py
"""

from __future__ import annotations

from .main import handle_event
from .schemas import RebookingOutcome


def _payload(customer_id: str, party_size: int, venue_id: str = "venue_42") -> dict:
    return {
        "reservation_id": f"rsv_test_{customer_id}",
        "venue_id": venue_id,
        "customer_id": customer_id,
        "party_size": party_size,
        "starts_at": "2026-06-05T19:00:00+00:00",
        "source": "resy",
    }


def test_platinum_party_within_window_rebooks() -> None:
    """Platinum tier + within-window slots + same source → action='rebooked'."""
    outcome: RebookingOutcome = handle_event(_payload("cust_7", party_size=4))
    assert outcome.action == "rebooked"
    assert outcome.new_reservation_id == "rsv_new_cust_7"
    assert outcome.notification_sent is True
    assert "Rebooked" in outcome.rationale


def test_standard_party_too_large_hits_host_only() -> None:
    """Standard tier + party_size>4 → eligibility denies → action='notify_host_only'."""
    outcome = handle_event(_payload("cust_13", party_size=6))
    assert outcome.action == "notify_host_only"
    # Tier rationale flowed through.
    assert "Standard tier" in outcome.rationale


def test_no_slots_declines() -> None:
    """Gold tier eligible but venue has no slots → action='declined'."""
    outcome = handle_event(_payload("cust_11", party_size=2, venue_id="venue_999"))
    assert outcome.action == "declined"
    assert "No alternative slots" in outcome.rationale


def test_unknown_customer_dlq() -> None:
    """Unknown customer_id → DLQ outcome (no party lookup)."""
    outcome = handle_event(_payload("cust_unknown", party_size=2))
    assert outcome.action == "dlq"
    assert "Unknown customer_id" in outcome.rationale
    assert outcome.notification_sent is False


def _run_all() -> None:
    """Smoke entry point — run every test as a plain function for ``python test_walkthrough.py``."""
    for fn in [
        test_platinum_party_within_window_rebooks,
        test_standard_party_too_large_hits_host_only,
        test_no_slots_declines,
        test_unknown_customer_dlq,
    ]:
        fn()
        print(f"PASS {fn.__name__}")
    print("All walkthrough cases passed.")


if __name__ == "__main__":
    _run_all()
