"""Restaurant-rebooking domain-example overlay for the Event-Driven pattern.

A worked example with concrete schemas, mock tools, role prompts, and
an end-to-end walkthrough. Anchored to
``agent-deployments/docs/recipes/restaurant-rebooking.md``.

Pattern: Event-Driven (consume → enrich → decide → act → emit).
See ``../../overview.md`` for the pattern's framework-agnostic shape.
"""

from .main import handle_event
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

__all__ = [
    "EligibilityDecision",
    "NotificationDraft",
    "Party",
    "RebookingOutcome",
    "Reservation",
    "Slot",
    "SlotRanking",
    "Tier",
    "handle_event",
]
