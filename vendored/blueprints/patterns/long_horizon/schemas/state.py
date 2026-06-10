"""Canonical Pydantic v2 state schema for the Long-Horizon pattern.

A task spans multiple worker processes and possibly weeks of wall-clock.
The runtime persists a Checkpoint snapshot + an append-only event log
and reconstructs state on resume by replaying events since the snapshot.
Self-contained — no cross-pattern imports.

See ``../design.md`` for the prose definition of each field.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

TaskStatus = Literal[
    "pending",
    "in_progress",
    "completed",
    "aborted",
    "requires_human",
    "deadline_exceeded",
]
StepStatus = Literal["pending", "in_progress", "completed", "failed", "skipped"]
EventKind = Literal[
    "task_started",
    "plan_emitted",
    "replanned",
    "step_started",
    "step_completed",
    "step_failed",
    "external_signal_received",
    "checkpoint_emitted",
    "human_escalation_requested",
    "task_completed",
    "task_aborted",
    "task_deadline_exceeded",
]


class StepRecord(BaseModel):
    """One step in the long-horizon plan."""

    step_id: str = Field(description="Stable id; persisted across resumes.")
    kind: str = Field(description="Step category (e.g. 'provision', 'wait_for_signal', 'human_review').")
    description: str = Field(description="What the step is supposed to accomplish.")
    status: StepStatus = "pending"
    attempt: int = Field(default=0, ge=0, description="Increments on retry.")
    started_at: datetime | None = None
    completed_at: datetime | None = None
    executor_role: str | None = Field(
        default=None,
        description="If this step delegates to a sub-agent, the role id.",
    )
    result: dict[str, object] = Field(
        default_factory=dict,
        description="Structured result the step produced; carries data forward to later steps.",
    )
    error: str | None = None
    idempotency_key: str | None = Field(
        default=None,
        description="Stable key downstream uses to deduplicate retries; usually derived from (task_id, step_id, attempt).",
    )


class Plan(BaseModel):
    """The current plan. Mutable across re-plans."""

    version: int = Field(default=0, ge=0, description="Bumped on every replan.")
    steps: list[StepRecord] = Field(default_factory=list)
    revised_at: datetime | None = None
    revision_reason: str | None = None

    def next_pending_step(self) -> StepRecord | None:
        for step in self.steps:
            if step.status == "pending":
                return step
        return None


class EventLogEntry(BaseModel):
    """One row in the append-only event log."""

    task_id: str
    seq: int = Field(ge=0, description="Monotonically increasing per task.")
    kind: EventKind
    payload: dict[str, object] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Checkpoint(BaseModel):
    """A snapshot of task state. Resume loads the latest checkpoint and replays events since."""

    task_id: str
    version: int = Field(ge=0, description="Monotonically increasing; matches the event-log seq at snapshot time.")
    state: LongHorizonState
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LongHorizonState(BaseModel):
    """Top-level state for a long-horizon task.

    Held in memory during a tick; persisted as a Checkpoint snapshot before
    the tick returns. Reducers apply events to advance the state.
    """

    task_id: str
    goal: str = Field(description="Free-text statement of what the task should accomplish.")
    status: TaskStatus = "pending"
    plan: Plan = Field(default_factory=Plan)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    deadline_at: datetime | None = Field(
        default=None,
        description="Overall task deadline; tick aborts the task on expiry.",
    )
    last_tick_at: datetime | None = None
    last_worker_id: str | None = None
    resume_count: int = Field(default=0, ge=0)
    replan_count: int = Field(default=0, ge=0)
    virtual_fs_root: str | None = Field(
        default=None,
        description="Per-task virtual filesystem root (e.g. 'gs://tasks/<task_id>/').",
    )
    metadata: dict[str, object] = Field(
        default_factory=dict,
        description="Free-form per-task metadata (tenant, owner, source trigger).",
    )

    @property
    def is_terminal(self) -> bool:
        return self.status in ("completed", "aborted", "requires_human", "deadline_exceeded")

    @property
    def completed_steps_count(self) -> int:
        return sum(1 for s in self.plan.steps if s.status == "completed")


# Rebuild forward references so Checkpoint can hold a LongHorizonState.
Checkpoint.model_rebuild()
