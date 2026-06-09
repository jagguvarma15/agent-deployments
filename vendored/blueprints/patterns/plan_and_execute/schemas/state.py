"""Canonical Pydantic v2 state schema for the Plan & Execute pattern.

A planner LLM produces a static ``Plan`` of ordered ``Step``s; an executor
walks the plan, producing an ``ExecutionResult`` per step. Optional
replanning loops feed an ``ExecutionResult`` summary back into the planner.

Recipes targeting Plan & Execute (e.g. ``code-review-agent.md``) reference
these names so the planner / executor / reflector roles agree on shape.
Self-contained — no cross-pattern imports.

See ``../design.md`` for the prose definition of each field.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Step(BaseModel):
    """One executable step in a plan."""

    id: str = Field(description="Stable id for cross-referencing in execution results.")
    description: str = Field(description="What the executor should do this step.")
    tool_hint: str | None = Field(
        default=None,
        description="Optional tool name the planner suggests; executor may override.",
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="Step ids that must complete before this step runs.",
    )


class Plan(BaseModel):
    """The planner's full output."""

    goal: str = Field(description="The objective the plan addresses.")
    steps: list[Step] = Field(min_length=1)
    rationale: str | None = Field(
        default=None,
        description="Why the planner chose this decomposition.",
    )


class ExecutionResult(BaseModel):
    """The executor's outcome for one Step."""

    step_id: str
    success: bool
    output: str = Field(description="Tool output or LLM synthesis for the step.")
    error: str | None = None


class PlanExecuteState(BaseModel):
    """Top-level state for a Plan & Execute run."""

    goal: str
    plan: Plan | None = Field(default=None)
    execution_results: list[ExecutionResult] = Field(default_factory=list)
    final_answer: str | None = Field(default=None)
    replans: int = Field(
        default=0,
        ge=0,
        description="How many times the planner was re-invoked after a failed execution.",
    )
    max_replans: int = Field(default=2, ge=0)
