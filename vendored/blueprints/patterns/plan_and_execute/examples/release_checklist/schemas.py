"""Domain schemas for the release-checklist plan-and-execute overlay.

Composes with the canonical Plan & Execute state in
``patterns/plan_and_execute/schemas/state.py`` (:class:`Plan`, :class:`Step`,
:class:`ExecutionResult`) and adds release-domain types: :class:`ReleaseEnv`
(target environment), :class:`ReleaseStepKind` (build / smoke / deploy /
verify), :class:`ReleasePlanStep` (a typed step with a kind tag and target
service), :class:`ReleasePlan` (top-level plan owning a sequence of steps
plus the release version), :class:`ReleaseStepResult` (per-step outcome
that wraps the canonical :class:`ExecutionResult` with a step-kind tag),
and :class:`ReplanDecision` (the replanner role's structured output: insert
a fix step before retry, abort, or proceed).

All Pydantic v2. Field descriptions surface to the LLM via the JSON
Schemas generated for tool / structured-output calls.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from patterns.plan_and_execute.schemas.state import (  # noqa: F401
    ExecutionResult,
    Plan,
    PlanExecuteState,
    Step,
)


class ReleaseEnv(str, Enum):
    """Target environment for a release run."""

    staging = "staging"
    production = "production"


class ReleaseStepKind(str, Enum):
    """The kind of work one step does. Drives executor dispatch."""

    build = "build"
    smoke = "smoke"
    deploy = "deploy"
    verify = "verify"
    fix = "fix"  # only inserted by the replanner after a smoke failure


class ReleasePlanStep(BaseModel):
    """One typed step in a release plan.

    Mirrors the canonical :class:`Step` shape (``id`` + ``description`` +
    optional ``tool_hint`` + ``depends_on``) and adds release-domain
    ``kind`` and ``target_service`` fields the executor dispatches on.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Stable step id; referenced by ReleaseStepResult.step_id.")
    kind: ReleaseStepKind
    target_service: str = Field(description="The service the step acts on (e.g. 'web', 'api').")
    description: str
    tool_hint: str | None = Field(
        default=None,
        description="Optional tool name the planner suggests; executor may override.",
    )
    depends_on: list[str] = Field(default_factory=list)


class ReleasePlan(BaseModel):
    """The planner's full output. Composes with canonical :class:`Plan`."""

    version: str = Field(description="Release version under deployment (semver string).")
    env: ReleaseEnv
    goal: str = Field(description="One-sentence statement of what success looks like.")
    steps: list[ReleasePlanStep] = Field(min_length=1)
    rationale: str | None = Field(
        default=None,
        description="Why the planner chose this decomposition.",
    )


class ReleaseStepResult(BaseModel):
    """One executor outcome.

    Wraps the canonical :class:`ExecutionResult` shape and tags the result
    with its :class:`ReleaseStepKind` so the replanner can decide whether
    a failure on this kind is worth a remediation step.
    """

    step_id: str
    kind: ReleaseStepKind
    success: bool
    output: str = Field(description="Tool output or executor synthesis.")
    error: str | None = None


class ReplanDecision(BaseModel):
    """The replanner role's structured output."""

    action: str = Field(
        description="`insert_fix` / `proceed` / `abort` — what to do after the failed step.",
    )
    fix_step: ReleasePlanStep | None = Field(
        default=None,
        description="The step to insert before the failed step's retry, when action is `insert_fix`.",
    )
    rationale: str
