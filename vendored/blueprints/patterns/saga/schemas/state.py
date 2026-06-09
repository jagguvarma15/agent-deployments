"""Canonical Pydantic v2 state schema for the Saga pattern.

A multi-step distributed transaction runs forward through ``SagaStep``s;
if any step fails, the coordinator runs ``Compensation``s for already-
completed steps in reverse order. Self-contained — no cross-pattern
imports.

See ``../design.md`` for the prose definition of each field.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SagaStatus = Literal["pending", "running", "succeeded", "failed", "compensating", "compensated"]


class SagaStep(BaseModel):
    """One forward step in a saga."""

    id: str = Field(description="Stable id; pairs with the matching Compensation.id.")
    name: str = Field(description="Human-readable label (e.g. 'reserve_seat').")
    status: SagaStatus = "pending"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    output: dict[str, object] = Field(
        default_factory=dict,
        description="Step result; carries data downstream steps may need.",
    )
    error: str | None = None


class Compensation(BaseModel):
    """An undo action for a previously-completed SagaStep."""

    id: str = Field(description="Matches the SagaStep.id it compensates.")
    name: str = Field(description="Human-readable label (e.g. 'release_seat').")
    status: SagaStatus = "pending"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    retry_count: int = Field(default=0, ge=0)


class SagaState(BaseModel):
    """Top-level state for one saga execution."""

    saga_id: str = Field(description="Stable id used in logs, traces, and idempotency keys.")
    status: SagaStatus = "pending"
    steps: list[SagaStep] = Field(min_length=1)
    compensations: list[Compensation] = Field(default_factory=list)
    failure_step_id: str | None = Field(
        default=None,
        description="Set when a step fails; identifies where compensation begins.",
    )
    metadata: dict[str, object] = Field(default_factory=dict)
