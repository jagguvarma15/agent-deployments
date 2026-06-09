"""Canonical Pydantic v2 state schema for the Event-Driven pattern.

A queue / topic delivers ``Event``s; each becomes a ``Case`` (enriched
with context the agent needs to decide); the loop produces an ``Outcome``
that is persisted and may emit follow-up events. Idempotency keys live on
``Event.event_id`` so re-deliveries are safe.

Recipes (``restaurant-rebooking.md``) reference these names so consumer /
decider / actor roles agree on shape. Self-contained — no cross-pattern
imports.

See ``../design.md`` for the prose definition of each field.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class Event(BaseModel):
    """An inbound event lifted off the queue."""

    event_id: str = Field(
        description="Deduplication key — the consumer must skip duplicates.",
    )
    event_type: str = Field(description="Routing discriminator (e.g. 'reservation.cancelled').")
    occurred_at: datetime
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, object] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)


class Case(BaseModel):
    """One enriched event ready for the decider."""

    event: Event
    enrichments: dict[str, object] = Field(
        default_factory=dict,
        description="Lookups (customer profile, policy, prior history) joined to the event.",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Cross-event id for tracing a longer flow.",
    )


class Outcome(BaseModel):
    """The result of acting on a Case."""

    case: Case
    action: str = Field(description="What the actor did (e.g. 'rebooked', 'declined').")
    success: bool = True
    error: str | None = None
    emitted_events: list[Event] = Field(
        default_factory=list,
        description="New events the actor produced; will be published downstream.",
    )
    persisted_keys: list[str] = Field(
        default_factory=list,
        description="DB / cache keys written; used for idempotent retry handling.",
    )


class EventDrivenState(BaseModel):
    """Top-level state for one event-handling cycle."""

    current_event: Event
    case: Case | None = Field(default=None)
    outcome: Outcome | None = Field(default=None)
    dlq_reason: str | None = Field(
        default=None,
        description="Set when the cycle terminates by routing the event to a dead-letter queue.",
    )
