"""Ops-crew domain-example overlay for the Multi-Agent pattern.

A worked example with concrete schemas, mock tools, role prompts, and
an end-to-end walkthrough. Anchored to
``agent-deployments/docs/recipes/ops-crew.md``.

Pattern: Multi-Agent (supervisor + flat crew of role peers).
See ``../../overview.md`` for the framework-agnostic shape.
"""

from .main import handle_incident
from .schemas import (
    IncidentReport,
    IncidentService,
    IncidentSignal,
    Runbook,
    RunbookExecution,
    RunbookStep,
    Severity,
    TriageDecision,
)

__all__ = [
    "IncidentReport",
    "IncidentService",
    "IncidentSignal",
    "Runbook",
    "RunbookExecution",
    "RunbookStep",
    "Severity",
    "TriageDecision",
    "handle_incident",
]
