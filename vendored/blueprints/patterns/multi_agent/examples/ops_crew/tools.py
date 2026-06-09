"""Concrete tool implementations for the ops-crew overlay.

Three adapters:

- ``PagerDutyAdapter.fetch_incident`` returns the raw ``IncidentSignal``
  from PagerDuty. Mocked against a small canned table; the real adapter
  would call ``GET /incidents/{id}``.
- ``runbook_lookup_find`` returns a ``Runbook`` by id. Mocked against a
  small library; the real lookup would hit a runbook store (Confluence,
  internal repo, etc.).
- ``SlackAdapter.post`` pretends to post the final ``IncidentReport`` to
  the incident channel. Mocked; real version calls ``chat.postMessage``.

The call signatures and return types are the contract that survives the
mock-to-real swap.
"""

from __future__ import annotations

import logging
from datetime import datetime

from .schemas import (
    IncidentReport,
    IncidentService,
    IncidentSignal,
    Runbook,
    RunbookStep,
    Severity,
)

log = logging.getLogger(__name__)

# ── Mock fixtures ────────────────────────────────────────────────────────────

_MOCK_INCIDENTS: dict[str, IncidentSignal] = {
    "inc_001": IncidentSignal(
        incident_id="inc_001",
        title="API p95 latency exceeded 2.5s for 5 minutes",
        body="GET /api/users started timing out at 18:42 UTC. /metrics shows db_pool_wait_ms > 1000.",
        service=IncidentService.api,
        severity_hint=Severity.sev2,
        occurred_at=datetime.fromisoformat("2026-06-05T18:42:00+00:00"),
        pagerduty_url="https://acme.pagerduty.com/incidents/inc_001",
    ),
    "inc_002": IncidentSignal(
        incident_id="inc_002",
        title="Auth service returning 500 for 3 IPs",
        body="3 client IPs hitting /auth/login are getting 500; one is internal CI runner.",
        service=IncidentService.auth,
        severity_hint=Severity.sev3,
        occurred_at=datetime.fromisoformat("2026-06-05T18:30:00+00:00"),
        pagerduty_url="https://acme.pagerduty.com/incidents/inc_002",
    ),
}

_MOCK_RUNBOOKS: dict[str, Runbook] = {
    "rb_db_pool_exhaustion": Runbook(
        runbook_id="rb_db_pool_exhaustion",
        title="DB pool exhaustion under API latency",
        steps=[
            RunbookStep(
                title="Check active query count",
                command="psql -c 'SELECT count(*) FROM pg_stat_activity;'",
                verifies="Returns a count; >150 confirms pool exhaustion.",
            ),
            RunbookStep(
                title="Identify long-running queries",
                command="psql -c 'SELECT pid, query_start, state, query FROM pg_stat_activity ORDER BY query_start LIMIT 5;'",
                verifies="Returns the oldest five queries.",
            ),
            RunbookStep(
                title="Restart API workers to drop stale connections",
                command="kubectl rollout restart deployment/api -n prod",
                verifies="`kubectl rollout status` reports the new ReplicaSet healthy.",
            ),
        ],
    ),
    "rb_auth_500": Runbook(
        runbook_id="rb_auth_500",
        title="Auth service 500 triage",
        steps=[
            RunbookStep(
                title="Check auth service logs",
                command="kubectl logs deployment/auth -n prod --tail=200",
                verifies="Returns recent log lines.",
            ),
            RunbookStep(
                title="Verify JWT signing key rotation status",
                command="vault kv get secret/auth/jwt",
                verifies="Returns the key + a `last_rotated_at` timestamp.",
            ),
        ],
    ),
}


# ── PagerDuty adapter ────────────────────────────────────────────────────────


class PagerDutyAdapter:
    """Wraps the PagerDuty incidents endpoint.

    Real shape:
        GET https://api.pagerduty.com/incidents/{id}
        Headers: Authorization: Token token=...
        Response: {"incident": {"id", "title", "description", "service", ...}}
    """

    def fetch_incident(self, incident_id: str) -> IncidentSignal:
        try:
            signal = _MOCK_INCIDENTS[incident_id]
        except KeyError as exc:
            raise LookupError(f"Unknown incident {incident_id!r}") from exc
        log.info("pagerduty.fetch_incident id=%s", incident_id)
        return signal


# ── Runbook lookup ───────────────────────────────────────────────────────────


def runbook_lookup_find(runbook_id: str | None, service: IncidentService) -> Runbook | None:
    """Return the runbook for ``runbook_id`` if known, otherwise fall back to
    a service-default. ``None`` means "no runbook covers this — page a human."""
    if runbook_id and runbook_id in _MOCK_RUNBOOKS:
        log.info("runbook.lookup hit id=%s", runbook_id)
        return _MOCK_RUNBOOKS[runbook_id]
    # Service-default fallback.
    defaults: dict[IncidentService, str] = {
        IncidentService.api: "rb_db_pool_exhaustion",
        IncidentService.auth: "rb_auth_500",
    }
    fallback = defaults.get(service)
    if fallback and fallback in _MOCK_RUNBOOKS:
        log.info("runbook.lookup fallback service=%s -> id=%s", service.value, fallback)
        return _MOCK_RUNBOOKS[fallback]
    return None


# ── Slack adapter ────────────────────────────────────────────────────────────


class SlackAdapter:
    """Wraps the Slack chat.postMessage API.

    Real shape:
        POST https://slack.com/api/chat.postMessage
        Form: channel, text, blocks (JSON)
    """

    def post(self, channel: str, report: IncidentReport) -> dict[str, object]:
        log.info("slack.post channel=%s incident=%s severity=%s", channel, report.incident_id, report.severity.value)
        return {"ok": True, "ts": "1717593720.000100"}
