# Domain example: Ops crew (multi-agent)

> Concrete worked example for the [Multi-Agent pattern](../overview.md), anchored to the [`ops-crew`](https://github.com/jagguvarma15/agent-deployments/blob/main/docs/recipes/ops-crew.md) recipe. The companion mini-project lives in [`ops_crew/`](ops_crew/) and runs offline.

## 1. Recipe context

`ops-crew` is the design-spec recipe for a small crew that handles inbound on-call incidents. PagerDuty fires; the crew triages, finds the matching runbook, executes it (or escalates), and posts a structured incident report to Slack. The recipe ships the topology (three role peers under a supervisor) and the framework (CrewAI / Vercel AI SDK); this overlay fills in the business-logic layer: what `pagerduty_adapter.fetch_incident()` returns, what `runbook_lookup.find()` looks like, what an `IncidentReport` ends up containing.

Read the recipe first for architecture, then this overlay for shapes and prompts.

## 2. Concrete domain glossary

| Term | Definition |
|------|------------|
| **IncidentSignal** | Raw alert shape from PagerDuty — `incident_id`, `title`, `body`, `service`, `severity_hint`, `occurred_at`, `pagerduty_url`. |
| **IncidentService** | Sub-system the incident is rooted in — one of `api / db / queue / network / auth`. Drives runbook selection. |
| **Severity** | `sev1 / sev2 / sev3 / sev4`. The triage role assigns the canonical severity (the hint from PagerDuty is advisory). |
| **TriageDecision** | The triage role's output — `severity`, `confidence`, optional `runbook_id`, `rationale`. |
| **Runbook** | A named, ordered list of `RunbookStep` entries; each step has a title, optional command, and a `verifies` clause. |
| **RunbookExecution** | The executor role's output — `runbook_id`, `steps_run`, `succeeded`, optional `failed_step`, `notes`. |
| **IncidentReport** | The incident_writer role's terminal output — `incident_id`, `severity`, `summary`, `timeline`, `follow_ups`, `slack_channel`. |

## 3. Concrete data

Two example incidents the crew handles:

```json
{"incident_id": "inc_001", "title": "API p95 latency exceeded 2.5s for 5 minutes", "body": "GET /api/users started timing out at 18:42 UTC. /metrics shows db_pool_wait_ms > 1000.", "service": "api",  "severity_hint": "sev2", "occurred_at": "2026-06-05T18:42:00+00:00"}
{"incident_id": "inc_002", "title": "Auth service returning 500 for 3 IPs",         "body": "3 client IPs hitting /auth/login are getting 500; one is internal CI runner.",                          "service": "auth", "severity_hint": "sev3", "occurred_at": "2026-06-05T18:30:00+00:00"}
```

Corresponding triage decisions (the role's structured output):

```json
{"incident_id": "inc_001", "severity": "sev2", "confidence": 0.9, "runbook_id": "rb_db_pool_exhaustion", "rationale": "API latency rooted in db_pool_wait_ms — known signature."}
{"incident_id": "inc_002", "severity": "sev3", "confidence": 0.8, "runbook_id": "rb_auth_500",          "rationale": "Auth 500s on a small IP set — service-default runbook applies."}
```

And one terminal `IncidentReport`:

```json
{
  "incident_id": "inc_001",
  "severity": "sev2",
  "summary": "Severity sev2: API p95 latency exceeded 2.5s for 5 minutes. Root cause: API latency rooted in db_pool_wait_ms — known signature. Ran runbook rb_db_pool_exhaustion (3 steps) and recovered service.",
  "timeline": [
    "2026-06-05T18:42:00+00:00 — incident raised: API p95 latency exceeded 2.5s for 5 minutes",
    "2026-06-05T18:42:00+00:00 — triage: severity=sev2, runbook=rb_db_pool_exhaustion",
    "2026-06-05T18:43:11+00:00 — runbook rb_db_pool_exhaustion executed: 3 steps, succeeded"
  ],
  "follow_ups": [],
  "slack_channel": "#incident-inc_001"
}
```

## 4. Concrete tool implementations

Full Python in [`ops_crew/tools.py`](ops_crew/tools.py).

- **`PagerDutyAdapter.fetch_incident(incident_id) -> IncidentSignal`** — wraps `GET https://api.pagerduty.com/incidents/{id}`. Mock body returns from a small canned table; raises `LookupError` for unknown ids.
- **`runbook_lookup_find(runbook_id, service) -> Runbook | None`** — returns the named runbook when known; falls back to a service-default (`api → rb_db_pool_exhaustion`, `auth → rb_auth_500`); returns `None` when no runbook covers the service so the writer can populate a follow-up.
- **`SlackAdapter.post(channel, report) -> {ok, ts}`** — wraps Slack's `chat.postMessage`. Mock returns `{"ok": True, "ts": "..."}`.

The mock-body / real-API split is the contract the recipe pins. Real adapters swap the bodies; the call signatures stay constant so the orchestrator code is unchanged.

## 5. Per-role prompts

Full strings in [`ops_crew/prompts.py`](ops_crew/prompts.py). Three roles, each typed input → typed output:

- **`triage`** — input: `IncidentSignal`. output: `TriageDecision`. The severity ladder + symptom→runbook mapping live in the prompt body. The role assigns confidence 0.5 when the runbook match is by service-default rather than symptom signature.
- **`runbook_executor`** — input: `Runbook`. output: `RunbookExecution`. Walks steps in declared order, examines each `verifies` clause, stops at the first failed verification, populates `failed_step`.
- **`incident_writer`** — input: `TriageDecision + RunbookExecution + IncidentSignal`. output: `IncidentReport`. Style guide: 2-3 sentence summary, ISO-timestamped timeline bullets, concrete owned follow-ups, channel is `#incident-<id>` unless sev1 → `#incidents-active`. Tone is factual / terse / no emojis.

Sample dialog for `triage`:

```
[system] You are the triage step of an ops crew...
[user]   IncidentSignal: {"incident_id": "inc_001", "service": "api", "body": "GET /api/users started timing out... db_pool_wait_ms > 1000.", ...}
[assistant — JSON]
{"severity": "sev2", "confidence": 0.9, "runbook_id": "rb_db_pool_exhaustion", "rationale": "API latency rooted in db_pool_wait_ms — known signature."}
```

## 6. Decision schemas

Pydantic v2 models in [`ops_crew/schemas.py`](ops_crew/schemas.py):

```python
class TriageDecision(BaseModel):
    severity: Severity        # sev1 | sev2 | sev3 | sev4
    confidence: float         # 0..1
    runbook_id: str | None
    rationale: str


class RunbookExecution(BaseModel):
    runbook_id: str
    steps_run: int
    succeeded: bool
    failed_step: str | None = None
    notes: list[str]


class IncidentReport(BaseModel):
    incident_id: str
    severity: Severity
    summary: str              # 2-3 sentences
    timeline: list[str]       # ISO-timestamped bullets
    follow_ups: list[str]
    slack_channel: str        # `#incident-<id>` unless sev1
```

These compose with the canonical Multi-Agent state in [`../schemas/state.py`](../schemas/state.py): the supervisor's per-role `AgentResult` + `SupervisorDecision` wrap the domain types here.

## 7. End-to-end walkthrough

Trace from `inc_001` (the API latency incident):

1. **Supervisor receives the incident id.** `handle_incident("inc_001")` in [`main.py`](ops_crew/main.py).
2. **Fetch.** `PagerDutyAdapter.fetch_incident("inc_001")` returns the typed `IncidentSignal` with `service="api"`, `body` mentioning `db_pool_wait_ms > 1000`.
3. **Triage role.** `_triage(signal)` matches `service=api + 'db_pool_wait_ms' in body` → returns `TriageDecision(severity=sev2, confidence=0.9, runbook_id="rb_db_pool_exhaustion", rationale="API latency rooted in db_pool_wait_ms — known signature.")`.
4. **Runbook lookup.** `runbook_lookup_find("rb_db_pool_exhaustion", IncidentService.api)` returns the runbook directly (named-id hit, not service-default).
5. **Executor role.** `_execute_runbook(runbook)` walks all three steps (check active queries → identify long-runners → restart workers); none fail their `verifies` clause → returns `RunbookExecution(steps_run=3, succeeded=True, notes=[...])`.
6. **Writer role.** `_write_report(signal, triage, execution)` produces the `IncidentReport` shown above: severity-aware summary, three-bullet timeline, channel `#incident-inc_001`, no follow-ups (success path).
7. **Post.** `SlackAdapter.post("#incident-inc_001", report)` returns `{"ok": True, "ts": ...}`. The supervisor returns the report to the caller (a webhook handler or on-call console).

The test suite ([`ops_crew/test_walkthrough.py`](ops_crew/test_walkthrough.py)) covers: api-latency → db-pool runbook, auth-500 → auth runbook, unknown-incident → `LookupError`. All offline.

## Run it

```bash
cd patterns/multi_agent/examples/ops_crew
uv run --with pydantic python -m patterns.multi-agent.examples.ops_crew.main
# or
uv run --with pydantic --with pytest python -m pytest test_walkthrough.py -v
```
