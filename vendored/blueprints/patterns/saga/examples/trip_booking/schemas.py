"""Domain schemas for the trip-booking saga overlay.

Composes with the canonical Saga state in
``patterns/saga/schemas/state.py`` (:class:`SagaStep`,
:class:`Compensation`, :class:`SagaState`) and adds trip-domain types:
:class:`LegKind` (flight / hotel / car), :class:`Leg` (one leg with its
booking parameters), :class:`Reservation` (the typed result of a
successful leg booking), :class:`CompensationOutcome` (per-leg
compensation status), :class:`SagaTerminalState` (the three legal end
states: ``completed`` / ``compensated`` / ``partially_compensated``),
:class:`TripBooking` (the input — three legs), :class:`TripResult` (the
output — every leg's reservation status plus the saga's terminal state).

All Pydantic v2. Field descriptions surface to the LLM via the JSON
Schemas generated for tool / structured-output calls.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from patterns.saga.schemas.state import Compensation, SagaState, SagaStep  # noqa: F401


class LegKind(str, Enum):
    """The three leg kinds the trip-booking saga handles."""

    flight = "flight"
    hotel = "hotel"
    car = "car"


class SagaTerminalState(str, Enum):
    """The three legal end states of a saga run."""

    completed = "completed"
    compensated = "compensated"
    partially_compensated = "partially_compensated"


class Leg(BaseModel):
    """One leg of a trip the saga forward-books."""

    model_config = ConfigDict(frozen=True)

    leg_id: str = Field(description="Stable id; pairs with the matching SagaStep / Compensation.")
    kind: LegKind
    vendor: str = Field(description="Provider slug (e.g. 'alpha-air', 'beta-stays', 'gamma-cars').")
    starts_at: datetime
    ends_at: datetime
    params: dict[str, str] = Field(
        default_factory=dict,
        description="Booking parameters specific to the leg kind (route, room class, car size).",
    )


class Reservation(BaseModel):
    """The booking adapter's typed response."""

    leg_id: str
    confirmation: str = Field(description="Vendor-issued confirmation code.")
    price_cents: int = Field(ge=0)
    booked_at: datetime


class CompensationOutcome(BaseModel):
    """Per-leg compensation status."""

    leg_id: str
    succeeded: bool
    error: str | None = None
    retry_count: int = Field(default=0, ge=0)


class TripBooking(BaseModel):
    """The saga's input — exactly three legs (flight + hotel + car)."""

    saga_id: str = Field(description="Stable id used in logs, traces, idempotency keys.")
    legs: list[Leg] = Field(min_length=3, max_length=3)


class TripResult(BaseModel):
    """The saga's typed output."""

    saga_id: str
    terminal_state: SagaTerminalState
    reservations: list[Reservation] = Field(default_factory=list)
    compensation_outcomes: list[CompensationOutcome] = Field(default_factory=list)
    failure_leg_id: str | None = Field(
        default=None,
        description="Set when terminal_state is `compensated` or `partially_compensated`.",
    )
