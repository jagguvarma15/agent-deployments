"""Trip-booking domain-example overlay for the Saga pattern.

A worked example with concrete schemas, mock tools, role prompts, and
an end-to-end walkthrough. No `agent-deployments` recipe anchors this
yet; the overlay below is the proposed shape.

Pattern: Saga (forward step + matching compensation on failure).
See ``../../overview.md`` for the framework-agnostic shape.
"""

from .main import book_trip
from .schemas import (
    CompensationOutcome,
    Leg,
    LegKind,
    Reservation,
    SagaTerminalState,
    TripBooking,
    TripResult,
)

__all__ = [
    "CompensationOutcome",
    "Leg",
    "LegKind",
    "Reservation",
    "SagaTerminalState",
    "TripBooking",
    "TripResult",
    "book_trip",
]
