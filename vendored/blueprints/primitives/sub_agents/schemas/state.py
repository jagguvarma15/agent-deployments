"""Canonical Pydantic v2 state schema for the Sub-agents primitive.

A parent agent spawns role-scoped sub-agent instances for delimited tasks.
Recipes that compose sub-agents (e.g. claude-code-subagent, research-team)
reference these names so frameworks can ground the registry, the spawn
contract, and the structured handoff against a shared shape. Self-contained
— no cross-pattern imports.

See ``../design.md`` for the prose definition of each field.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

TerminationReason = Literal[
    "completed",
    "cap_hit",
    "deadline",
    "tool_denied",
    "schema_error",
    "error",
]


class Limits(BaseModel):
    """Per-role caps that bound the sub-agent loop."""

    max_steps: int = Field(default=10, ge=1)
    max_tokens_in: int = Field(default=80_000, ge=1)
    max_tokens_out: int = Field(default=4_000, ge=1)
    max_tool_calls: int = Field(default=20, ge=0)
    deadline_seconds: int = Field(default=180, ge=1)


class SubAgentSpec(BaseModel):
    """One entry in the sub-agent registry, built at boot from ROLE.md + tools.yaml + result-schema.json."""

    role_id: str = Field(description="Kebab-case identifier; unique in the registry.")
    name: str = Field(description="Human-readable label.")
    version: str = Field(description="Semver; bumped when system prompt or schema changes.")
    description: str = Field(description="One-line purpose; the parent reads this when deciding to delegate.")
    system_prompt: str = Field(description="The role's system prompt — body of ROLE.md.")
    allowed_tools: list[str] = Field(
        default_factory=list,
        description="Tool ids the sub-agent can use; the harness denies everything else.",
    )
    model: str = Field(
        description="Model id for this role (e.g. 'haiku', 'sonnet', 'opus', 'external:my-finetune').",
    )
    result_schema_path: str = Field(description="Filesystem path to result-schema.json.")
    when_to_spawn: str | None = Field(
        default=None,
        description="Hint the parent uses for role selection.",
    )
    limits: Limits = Field(default_factory=Limits)


class ContextEnvelope(BaseModel):
    """What the parent hands the sub-agent at spawn time.

    Deliberately small — passing too much context is the most common bug.
    Do not pass the parent's raw transcript here.
    """

    task_description: str = Field(description="Short description of what the sub-agent should do.")
    inputs: dict[str, object] = Field(
        default_factory=dict,
        description="Structured inputs (ids, keys, parameters) the sub-agent needs.",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Free-text constraints (e.g. 'do not contact the legacy API').",
    )
    upstream_results: dict[str, dict] | None = Field(
        default=None,
        description="Structured results from earlier sub-agents in the same parent request, if any.",
    )


class SubAgentInvocation(BaseModel):
    """One spawn event. Persisted regardless of outcome."""

    invocation_id: str = Field(description="Unique per spawn.")
    parent_id: str = Field(description="Id of the parent agent / request.")
    role_id: str = Field(description="Spec.role_id at spawn time.")
    spec_version: str = Field(description="Spec.version at spawn time; result consumers check compat.")
    spawned_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deadline_at: datetime | None = Field(default=None)


class SubAgentResult(BaseModel):
    """The structured handoff back to the parent."""

    invocation_id: str
    role_id: str
    payload: dict = Field(
        description="The structured result; MUST match result-schema.json for the role.",
    )
    termination: TerminationReason
    steps_taken: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    error: str | None = Field(
        default=None,
        description="If termination='error' or 'tool_denied', a short diagnostic.",
    )
    finished_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SubAgentsState(BaseModel):
    """Per-request state the parent maintains about its sub-agent fan-out.

    Recipes can consult this state for trace emission, merge strategy
    selection, and after-the-fact accounting.
    """

    parent_id: str
    invocations: list[SubAgentInvocation] = Field(default_factory=list)
    results: list[SubAgentResult] = Field(default_factory=list)
    pending_role_ids: list[str] = Field(
        default_factory=list,
        description="Roles the parent intends to spawn but hasn't yet.",
    )
    max_recursion_depth: int = Field(
        default=2,
        ge=0,
        description="Hard cap on nesting; harness enforces.",
    )

    @property
    def total_tokens_in(self) -> int:
        return sum(r.tokens_in for r in self.results)

    @property
    def total_tokens_out(self) -> int:
        return sum(r.tokens_out for r in self.results)

    @property
    def degraded_count(self) -> int:
        return sum(1 for r in self.results if r.termination != "completed")
