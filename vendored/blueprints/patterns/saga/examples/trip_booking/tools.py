"""Mock adapters for the trip-booking saga overlay.

Three booking surfaces (flight / hotel / car), each with a book / cancel
pair so the saga can compensate on failure. The mocks honour per-leg
failure scenarios in a small canned table so the walkthrough can
exercise all three terminal states (`completed`, `compensated`,
`partially_compensated`).

Real adapters wrap the vendor APIs (Amadeus, Sabre, etc.) and swap the
mock bodies. Call signatures stay constant so the coordinator code is
unchanged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .schemas import LegKind, Reservation

log = logging.getLogger(__name__)


# ── Canned failure scenarios ─────────────────────────────────────────────────


# Saga ids whose forward booking of one leg fails. The saga's
# compensation chain walks the previously-completed legs in reverse.
_BOOK_FAILURES: dict[str, str] = {
    # trip_002 + trip_003: car booking fails -> flight + hotel must
    # compensate. trip_003 also has a compensation-side failure on the
    # hotel cancel below so the run terminates as partially_compensated.
    "trip_002": "car",
    "trip_003": "car",
}

# Per-leg cancel failures. Used to exercise the partially_compensated
# terminal state — the coordinator classifies recoverable errors as
# continue-compensating, so the remaining legs still get cancelled but
# the saga's terminal state carries the residual.
_COMPENSATE_FAILURES: dict[tuple[str, str], str] = {
    ("trip_003", "hotel"): "vendor_timeout",
}


# ── Adapters ────────────────────────────────────────────────────────────────


@dataclass
class FlightAdapter:
    """Mock flight booking. book + cancel pair."""

    bookings: dict[str, Reservation] = field(default_factory=dict)

    def book(self, saga_id: str, leg_id: str, vendor: str) -> Reservation:
        if _BOOK_FAILURES.get(saga_id) == "flight":
            raise RuntimeError(f"flight booking failed: vendor={vendor}")
        res = Reservation(
            leg_id=leg_id,
            confirmation=f"FL-{saga_id[-3:]}-{vendor[:3]}",
            price_cents=42_000,
            booked_at=datetime.now(UTC),
        )
        self.bookings[leg_id] = res
        return res

    def cancel(self, saga_id: str, leg_id: str) -> None:
        if (saga_id, "flight") in _COMPENSATE_FAILURES:
            raise RuntimeError(f"flight cancellation failed: {_COMPENSATE_FAILURES[(saga_id, 'flight')]}")
        self.bookings.pop(leg_id, None)


@dataclass
class HotelAdapter:
    """Mock hotel booking. book + cancel pair."""

    bookings: dict[str, Reservation] = field(default_factory=dict)

    def book(self, saga_id: str, leg_id: str, vendor: str) -> Reservation:
        if _BOOK_FAILURES.get(saga_id) == "hotel":
            raise RuntimeError(f"hotel booking failed: vendor={vendor}")
        res = Reservation(
            leg_id=leg_id,
            confirmation=f"HT-{saga_id[-3:]}-{vendor[:3]}",
            price_cents=21_500,
            booked_at=datetime.now(UTC),
        )
        self.bookings[leg_id] = res
        return res

    def cancel(self, saga_id: str, leg_id: str) -> None:
        if (saga_id, "hotel") in _COMPENSATE_FAILURES:
            raise RuntimeError(f"hotel cancellation failed: {_COMPENSATE_FAILURES[(saga_id, 'hotel')]}")
        self.bookings.pop(leg_id, None)


@dataclass
class CarAdapter:
    """Mock car booking. book + cancel pair."""

    bookings: dict[str, Reservation] = field(default_factory=dict)

    def book(self, saga_id: str, leg_id: str, vendor: str) -> Reservation:
        if _BOOK_FAILURES.get(saga_id) == "car":
            raise RuntimeError(f"car booking failed: vendor={vendor}")
        res = Reservation(
            leg_id=leg_id,
            confirmation=f"CR-{saga_id[-3:]}-{vendor[:3]}",
            price_cents=9_800,
            booked_at=datetime.now(UTC),
        )
        self.bookings[leg_id] = res
        return res

    def cancel(self, saga_id: str, leg_id: str) -> None:
        if (saga_id, "car") in _COMPENSATE_FAILURES:
            raise RuntimeError(f"car cancellation failed: {_COMPENSATE_FAILURES[(saga_id, 'car')]}")
        self.bookings.pop(leg_id, None)


@dataclass
class AuditLog:
    """In-memory append-only log; real impl writes to Postgres + ships to S3."""

    entries: list[dict[str, str]] = field(default_factory=list)

    def append(self, saga_id: str, event: str, detail: str = "") -> None:
        self.entries.append({"saga_id": saga_id, "event": event, "detail": detail})
        log.info("audit", extra={"saga_id": saga_id, "event": event, "detail": detail})


# ── Dispatch helpers ────────────────────────────────────────────────────────


def book_leg(adapter, saga_id: str, leg_id: str, vendor: str) -> Reservation:
    return adapter.book(saga_id, leg_id, vendor)


def cancel_leg(adapter, saga_id: str, leg_id: str) -> None:
    adapter.cancel(saga_id, leg_id)


def adapter_for_kind(
    kind: LegKind,
    flight: FlightAdapter,
    hotel: HotelAdapter,
    car: CarAdapter,
) -> FlightAdapter | HotelAdapter | CarAdapter:
    if kind is LegKind.flight:
        return flight
    if kind is LegKind.hotel:
        return hotel
    return car
