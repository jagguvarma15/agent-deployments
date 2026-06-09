"""End-to-end walkthrough wiring for the trip-booking saga overlay.

Composes the schemas, tools, and prompts into a ``book_trip`` entry
point that takes a :class:`TripBooking` and returns a
:class:`TripResult` with the saga's terminal state plus every leg's
reservation status and compensation outcome.

The forward saga is deterministic — book flight, then hotel, then car,
in that order. The optional coordinator role (consulted only when a
compensation itself fails) is a deterministic stub here so the
walkthrough runs offline; production swaps it for an ``anthropic``
``Agent`` call against ``COORDINATOR_SYSTEM_PROMPT``.

Pattern this composes: Saga (forward step + matching compensation). See
``../../overview.md`` for the framework-agnostic shape and
``../../code/python/saga.py`` for the canonical sibling implementation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .schemas import (
    CompensationOutcome,
    Leg,
    LegKind,
    Reservation,
    SagaTerminalState,
    TripBooking,
    TripResult,
)
from .tools import (
    AuditLog,
    CarAdapter,
    FlightAdapter,
    HotelAdapter,
    adapter_for_kind,
    book_leg,
    cancel_leg,
)

log = logging.getLogger(__name__)


# ── coordinator role (stub for the LLM call) ─────────────────────────────────


@dataclass
class _CoordinatorDecision:
    action: str  # "continue_compensating" | "stop_with_partial"
    rationale: str
    notify_runbook: str | None = None


def _coordinator_decision(
    failed: CompensationOutcome,
    pending_leg_ids: list[str],
) -> _CoordinatorDecision:
    """Decide what to do when a compensation itself fails.

    Policy mirrors ``COORDINATOR_SYSTEM_PROMPT``: recoverable vendor errors
    let remaining compensations proceed; otherwise stop with a partial.
    """
    recoverable = failed.error in {"vendor_timeout"} if failed.error else False
    if recoverable and pending_leg_ids:
        return _CoordinatorDecision(
            action="continue_compensating",
            rationale=f"{failed.error} is retryable; do not block remaining undo work.",
        )
    return _CoordinatorDecision(
        action="stop_with_partial",
        rationale=f"compensation for {failed.leg_id} failed with {failed.error}; surface residual.",
        notify_runbook="rb_trip_partial_compensation",
    )


# ── coordinator: run one saga end-to-end ─────────────────────────────────────


@dataclass
class _SagaRuntime:
    """Holds the adapters + audit log for one saga run."""

    flight: FlightAdapter = field(default_factory=FlightAdapter)
    hotel: HotelAdapter = field(default_factory=HotelAdapter)
    car: CarAdapter = field(default_factory=CarAdapter)
    audit: AuditLog = field(default_factory=AuditLog)


def _book_leg_and_record(
    runtime: _SagaRuntime,
    saga_id: str,
    leg: Leg,
    reservations: list[Reservation],
    completed: list[Leg],
) -> Exception | None:
    """Book one leg; on failure, return the exception so the caller can compensate."""
    adapter = adapter_for_kind(leg.kind, runtime.flight, runtime.hotel, runtime.car)
    try:
        res = book_leg(adapter, saga_id, leg.leg_id, leg.vendor)
    except Exception as exc:
        runtime.audit.append(saga_id, "leg_booking_failed", f"{leg.leg_id}: {exc}")
        return exc
    reservations.append(res)
    completed.append(leg)
    runtime.audit.append(saga_id, "leg_booked", f"{leg.leg_id}: {res.confirmation}")
    return None


def _compensate(
    runtime: _SagaRuntime,
    saga_id: str,
    completed: list[Leg],
) -> tuple[list[CompensationOutcome], bool]:
    """Walk completed legs in reverse and cancel each. Returns the
    compensation outcomes plus a flag for whether every cancellation
    succeeded. On a compensation failure, the coordinator decides
    whether to continue or stop early."""

    outcomes: list[CompensationOutcome] = []
    pending: list[Leg] = list(reversed(completed))
    any_failure = False

    while pending:
        leg = pending.pop(0)
        adapter = adapter_for_kind(leg.kind, runtime.flight, runtime.hotel, runtime.car)
        try:
            cancel_leg(adapter, saga_id, leg.leg_id)
        except Exception as exc:
            outcome = CompensationOutcome(leg_id=leg.leg_id, succeeded=False, error=str(exc).split(":")[-1].strip())
            outcomes.append(outcome)
            any_failure = True
            decision = _coordinator_decision(outcome, [p.leg_id for p in pending])
            runtime.audit.append(
                saga_id,
                "coordinator_decision",
                f"{leg.leg_id}: action={decision.action} rationale={decision.rationale}",
            )
            if decision.action == "stop_with_partial":
                # Mark the still-pending legs' compensations as unattempted; the
                # runbook the coordinator named takes over from here.
                for unattempted in pending:
                    outcomes.append(
                        CompensationOutcome(
                            leg_id=unattempted.leg_id,
                            succeeded=False,
                            error="not_attempted",
                        ),
                    )
                return outcomes, False
            continue
        outcomes.append(CompensationOutcome(leg_id=leg.leg_id, succeeded=True))
        runtime.audit.append(saga_id, "leg_compensated", leg.leg_id)

    return outcomes, not any_failure


def book_trip(booking: TripBooking) -> TripResult:
    """Forward-book each leg; on failure, compensate completed legs in reverse."""

    runtime = _SagaRuntime()
    saga_id = booking.saga_id
    runtime.audit.append(saga_id, "saga_started")

    reservations: list[Reservation] = []
    completed: list[Leg] = []
    failure_leg_id: str | None = None

    for leg in booking.legs:
        err = _book_leg_and_record(runtime, saga_id, leg, reservations, completed)
        if err is not None:
            failure_leg_id = leg.leg_id
            break

    if failure_leg_id is None:
        runtime.audit.append(saga_id, "saga_completed")
        return TripResult(
            saga_id=saga_id,
            terminal_state=SagaTerminalState.completed,
            reservations=reservations,
        )

    outcomes, all_compensated = _compensate(runtime, saga_id, completed)
    terminal = SagaTerminalState.compensated if all_compensated else SagaTerminalState.partially_compensated
    runtime.audit.append(saga_id, terminal.value)

    return TripResult(
        saga_id=saga_id,
        terminal_state=terminal,
        reservations=reservations,
        compensation_outcomes=outcomes,
        failure_leg_id=failure_leg_id,
    )


# ── Demo bookings ────────────────────────────────────────────────────────────


def _sample_booking(saga_id: str) -> TripBooking:
    """Build a canonical 3-leg trip the demo uses."""
    base = datetime(2026, 7, 4, 9, 0, tzinfo=UTC)
    return TripBooking(
        saga_id=saga_id,
        legs=[
            Leg(
                leg_id=f"{saga_id}-flight",
                kind=LegKind.flight,
                vendor="alpha-air",
                starts_at=base,
                ends_at=base.replace(hour=14),
                params={"route": "SFO-JFK"},
            ),
            Leg(
                leg_id=f"{saga_id}-hotel",
                kind=LegKind.hotel,
                vendor="beta-stays",
                starts_at=base.replace(hour=16),
                ends_at=base.replace(day=11),
                params={"room": "queen"},
            ),
            Leg(
                leg_id=f"{saga_id}-car",
                kind=LegKind.car,
                vendor="gamma-cars",
                starts_at=base.replace(hour=15),
                ends_at=base.replace(day=11),
                params={"size": "midsize"},
            ),
        ],
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for saga_id in ["trip_001", "trip_002", "trip_003"]:
        result = book_trip(_sample_booking(saga_id))
        print(f"{saga_id} -> {result.terminal_state.value}")
        for r in result.reservations:
            print(f"  reserved {r.leg_id}: {r.confirmation}")
        for o in result.compensation_outcomes:
            tag = "ok" if o.succeeded else f"fail ({o.error})"
            print(f"  compensation {o.leg_id}: {tag}")
        if result.failure_leg_id:
            print(f"  failure_leg_id={result.failure_leg_id}")
