"""Domain schemas for the ops-crew multi-agent overlay.

Three roles — triage, runbook_executor, incident_writer — each consume
typed inputs and produce typed outputs. Composes with the canonical
multi-agent state in ``patterns/multi_agent/schemas/state.py``:
:class:`IncidentReport` (the writer role's output) carries an
``agent_results`` field of canonical :class:`AgentResult` so each crew
member's contribution is visible end-to-end without the overlay having
to re-derive a step trail.

All Pydantic v2.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from patterns.multi_agent.schemas.state import AgentResult, MultiAgentState  # noqa: F401


class Severity(str, Enum):
    sev1 = "sev1"
    sev2 = "sev2"
    sev3 = "sev3"
    sev4 = "sev4"


class IncidentService(str, Enum):
    """Sub-system the incident is rooted in. Drives runbook selection."""

    api = "api"
    db = "db"
    queue = "queue"
    network = "network"
    auth = "auth"


class IncidentSignal(BaseModel):
    """The raw alert shape PagerDuty hands us."""

    model_config = ConfigDict(frozen=True)

    incident_id: str
    title: str
    body: str
    service: IncidentService
    severity_hint: Severity | None = None
    occurred_at: datetime
    pagerduty_url: str = Field(description="Deep link back to the PagerDuty incident.")


class TriageDecision(BaseModel):
    """The triage role's structured output."""

    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    runbook_id: str | None = Field(
        default=None,
        description="If the triage role recognised a known runbook, its id. Otherwise None.",
    )
    rationale: str = Field(description="One sentence on the call.")


class RunbookStep(BaseModel):
    """One step the executor walks through."""

    title: str
    command: str | None = None
    verifies: str = Field(description="What the step's verification check returns on success.")


class Runbook(BaseModel):
    """A named runbook the executor follows."""

    runbook_id: str
    title: str
    steps: list[RunbookStep]


class RunbookExecution(BaseModel):
    """The executor role's output: which steps ran, which failed, what came back."""

    runbook_id: str
    steps_run: int
    succeeded: bool
    failed_step: str | None = None
    notes: list[str] = Field(default_factory=list)


class IncidentReport(BaseModel):
    """The incident_writer role's final structured output.

    What the crew hands back to the on-call when the flow finishes; gets
    posted to the incident's Slack channel and pasted into the post-mortem.

    ``agent_results`` carries the canonical
    :class:`patterns.multi_agent.schemas.state.AgentResult` for each crew
    member so per-agent traces and token costs survive past the report.
    """

    incident_id: str
    severity: Severity
    summary: str = Field(description="2-3 sentence executive summary.")
    timeline: list[str] = Field(
        description="Ordered bullet list — each is a one-line event with a timestamp.",
    )
    follow_ups: list[str] = Field(default_factory=list)
    slack_channel: str
    agent_results: list[AgentResult] = Field(
        default_factory=list,
        description="Per-crew-member contribution log in canonical AgentResult shape.",
    )
