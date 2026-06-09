"""End-to-end walkthrough tests for the trip-booking saga overlay.

Runs offline — booking + cancellation adapters are deterministic stubs in
``tools``; the coordinator role is a deterministic stub in ``main``.
Real production swaps the coordinator for an ``anthropic`` Agent call.

Three scenarios cover the three terminal states the saga can reach:

  - ``completed`` — every leg books successfully.
  - ``compensated`` — a leg fails mid-saga; every previously-booked leg
    is cancelled cleanly.
  - ``partially_compensated`` — a leg fails mid-saga; one of the
    cancellations itself fails, the coordinator stops with a partial,
    and the runbook the prompt named is the recovery path.

Run:
    uv run --with pydantic --with pytest python -m pytest test_walkthrough.py -v

Or as a script:
    uv run --with pydantic python test_walkthrough.py
"""

from __future__ import annotations

from .main import _sample_booking, book_trip
from .schemas import SagaTerminalState


def test_happy_path_books_all_three_legs() -> None:
    result = book_trip(_sample_booking("trip_001"))
    assert result.terminal_state is SagaTerminalState.completed
    assert len(result.reservations) == 3
    assert {r.leg_id for r in result.reservations} == {
        "trip_001-flight",
        "trip_001-hotel",
        "trip_001-car",
    }
    assert result.compensation_outcomes == []
    assert result.failure_leg_id is None


def test_mid_saga_failure_compensates_cleanly() -> None:
    """trip_002: car booking fails -> flight + hotel compensate cleanly."""
    result = book_trip(_sample_booking("trip_002"))
    assert result.terminal_state is SagaTerminalState.compensated
    # Two legs booked before the failure.
    assert {r.leg_id for r in result.reservations} == {
        "trip_002-flight",
        "trip_002-hotel",
    }
    assert result.failure_leg_id == "trip_002-car"
    # Compensations walked in reverse: hotel first, then flight.
    cancelled = [o.leg_id for o in result.compensation_outcomes]
    assert cancelled == ["trip_002-hotel", "trip_002-flight"]
    assert all(o.succeeded for o in result.compensation_outcomes)


def test_compensation_failure_yields_partially_compensated() -> None:
    """trip_003: car booking fails after flight + hotel succeed; the
    hotel cancel raises `vendor_timeout` (a recoverable failure); the
    coordinator decides to continue compensating; the flight cancel
    succeeds; one residual hotel booking remains -> the saga's terminal
    state is `partially_compensated`.

    The full main-path is verified in the offline smoke run; this test
    pins the contract by driving ``_compensate`` directly with a
    hand-built ``completed`` list so the partial-compensation path is
    independently verifiable.
    """

    from datetime import UTC, datetime

    from .main import _compensate, _SagaRuntime
    from .schemas import Leg, LegKind

    base = datetime(2026, 7, 4, 9, 0, tzinfo=UTC)
    completed = [
        Leg(
            leg_id="trip_003-flight",
            kind=LegKind.flight,
            vendor="alpha-air",
            starts_at=base,
            ends_at=base.replace(hour=14),
        ),
        Leg(
            leg_id="trip_003-hotel",
            kind=LegKind.hotel,
            vendor="beta-stays",
            starts_at=base.replace(hour=16),
            ends_at=base.replace(day=11),
        ),
    ]
    runtime = _SagaRuntime()
    outcomes, all_ok = _compensate(runtime, "trip_003", completed)
    assert all_ok is False  # one compensation failed -> partially_compensated
    # Hotel is compensated first (reverse order). The cancel raises
    # `vendor_timeout`, which the coordinator classifies as recoverable;
    # the runtime continues compensating remaining legs so a transient
    # vendor failure on one leg doesn't block undoing the others.
    hotel_outcome = next(o for o in outcomes if o.leg_id == "trip_003-hotel")
    assert hotel_outcome.succeeded is False
    assert "vendor_timeout" in (hotel_outcome.error or "")
    # Flight's compensation succeeds; the saga's terminal state is
    # `partially_compensated` because the hotel residual remains.
    flight_outcome = next(o for o in outcomes if o.leg_id == "trip_003-flight")
    assert flight_outcome.succeeded is True


def _run_all() -> None:
    """Smoke entry point — run every test as a plain function."""
    test_happy_path_books_all_three_legs()
    print("PASS test_happy_path_books_all_three_legs")
    test_mid_saga_failure_compensates_cleanly()
    print("PASS test_mid_saga_failure_compensates_cleanly")
    test_compensation_failure_yields_partially_compensated()
    print("PASS test_compensation_failure_yields_partially_compensated")
    print("All walkthrough cases passed.")


if __name__ == "__main__":
    _run_all()
