"""Release-checklist domain-example overlay for the Plan & Execute pattern.

A worked example with concrete schemas, mock tools, role prompts, and
an end-to-end walkthrough. No `agent-deployments` recipe anchors this
yet; the overlay below is the proposed shape.

Pattern: Plan & Execute (planner produces an ordered plan, executor
walks it, replanner inserts remediation steps on failure).
See ``../../overview.md`` for the framework-agnostic shape.
"""

from .main import run_release
from .schemas import (
    ReleaseEnv,
    ReleasePlan,
    ReleasePlanStep,
    ReleaseStepKind,
    ReleaseStepResult,
    ReplanDecision,
)

__all__ = [
    "ReleaseEnv",
    "ReleasePlan",
    "ReleasePlanStep",
    "ReleaseStepKind",
    "ReleaseStepResult",
    "ReplanDecision",
    "run_release",
]
