"""End-to-end walkthrough wiring for the ops-crew overlay.

Composes the schemas, tools, and prompts into a ``handle_incident``
entry point that takes a PagerDuty incident id and returns an
``IncidentReport``. The triage, executor, and writer roles are
deterministic stubs here (so the walkthrough runs offline); production
swaps each for an ``anthropic`` ``Agent`` call against the corresponding
system prompt.

Pattern this composes: Multi-Agent (supervisor → role peers). See
``../../overview.md`` and the recipe at
``agent-deployments/docs/recipes/ops-crew.md``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from .schemas import (
    IncidentReport,
    IncidentSignal,
    Runbook,
    RunbookExecution,
    Severity,
    TriageDecision,
)
from .tools import (
    PagerDutyAdapter,
    SlackAdapter,
    runbook_lookup_find,
)

log = logging.getLogger(__name__)

# ── triage role (stub for the LLM call) ──────────────────────────────────────


def _triage(signal: IncidentSignal) -> TriageDecision:
    body = signal.body.lower()
    title = signal.title.lower()

    # Service+symptom match rules — mirror TRIAGE_SYSTEM_PROMPT.
    if signal.service.value == "api" and "db_pool_wait_ms" in body:
        return TriageDecision(
            severity=Severity.sev2,
            confidence=0.9,
            runbook_id="rb_db_pool_exhaustion",
            rationale="API latency rooted in db_pool_wait_ms — known signature.",
        )
    if signal.service.value == "auth" and "500" in body or signal.service.value == "auth" and "500" in title:
        return TriageDecision(
            severity=Severity.sev3,
            confidence=0.8,
            runbook_id="rb_auth_500",
            rationale="Auth 500s on a small IP set — service-default runbook applies.",
        )
    # Service default fallback (lower confidence).
    return TriageDecision(
        severity=signal.severity_hint or Severity.sev3,
        confidence=0.5,
        runbook_id=None,
        rationale="No symptom signature matched; falling back to severity hint.",
    )


# ── runbook_executor role (stub for the LLM call) ────────────────────────────


def _execute_runbook(runbook: Runbook) -> RunbookExecution:
    """Walk every step, recording one note per step, no failures.

    Real production code would shell out / hit an SRE bot per step. The
    stub here keeps the walkthrough offline.
    """
    notes = [f"step {i + 1}: {step.title} — verified" for i, step in enumerate(runbook.steps)]
    return RunbookExecution(
        runbook_id=runbook.runbook_id,
        steps_run=len(runbook.steps),
        succeeded=True,
        notes=notes,
    )


# ── incident_writer role (stub for the LLM call) ─────────────────────────────


def _write_report(
    signal: IncidentSignal,
    triage: TriageDecision,
    execution: RunbookExecution | None,
) -> IncidentReport:
    timeline = [
        f"{signal.occurred_at.isoformat()} — incident raised: {signal.title}",
        f"{signal.occurred_at.isoformat()} — triage: severity={triage.severity.value}, runbook={triage.runbook_id or 'none'}",
    ]
    if execution is not None:
        timeline.append(
            f"{datetime.now(UTC).isoformat()} — runbook {execution.runbook_id} executed: "
            f"{execution.steps_run} steps, {'succeeded' if execution.succeeded else 'failed'}",
        )
        action_sentence = (
            f"Ran runbook {execution.runbook_id} ({execution.steps_run} steps) and recovered service."
            if execution.succeeded
            else f"Ran runbook {execution.runbook_id}; step {execution.failed_step!r} did not verify."
        )
    else:
        action_sentence = "No runbook matched; paged the on-call to handle by hand."

    summary = " ".join(
        [
            f"Severity {triage.severity.value}: {signal.title}.",
            f"Root cause: {triage.rationale}",
            action_sentence,
        ],
    )
    channel = "#incidents-active" if triage.severity == Severity.sev1 else f"#incident-{signal.incident_id}"
    follow_ups: list[str] = []
    if execution is not None and not execution.succeeded:
        follow_ups.append(f"Re-run failed step: {execution.failed_step}")
    if not execution:
        follow_ups.append("Author a runbook for this signature so the next incident auto-resolves.")

    return IncidentReport(
        incident_id=signal.incident_id,
        severity=triage.severity,
        summary=summary,
        timeline=timeline,
        follow_ups=follow_ups,
        slack_channel=channel,
    )


# ── supervisor: handle one incident end-to-end ──────────────────────────────


def handle_incident(incident_id: str) -> IncidentReport:
    pd = PagerDutyAdapter()
    signal = pd.fetch_incident(incident_id)

    triage = _triage(signal)
    runbook = runbook_lookup_find(triage.runbook_id, signal.service)
    execution = _execute_runbook(runbook) if runbook else None

    report = _write_report(signal, triage, execution)

    slack = SlackAdapter()
    slack.post(report.slack_channel, report)
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for incident_id in ["inc_001", "inc_002"]:
        report = handle_incident(incident_id)
        print(f"{incident_id} -> severity={report.severity.value} channel={report.slack_channel}")
        print(f"  summary: {report.summary}")
        for line in report.timeline:
            print(f"  -- {line}")
        for fu in report.follow_ups:
            print(f"  follow-up: {fu}")
