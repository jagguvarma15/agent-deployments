# Recipe: Ops Crew

**Status:** Blueprint (design spec)

**Composes:**

- Pattern: [Multi-Agent Flat](../patterns/multi-agent-flat.md)
- Framework (Py): [CrewAI](../frameworks/crewai.md) (Crew + Agent + Task)
- Framework (TS): [Vercel AI SDK](../frameworks/vercel-ai-sdk.md) (manual multi-agent orchestration)
- Stack: [FastAPI](../stack/api-fastapi.md) / [Hono](../stack/api-hono.md), [Postgres](../stack/relational-postgres.md), [Redis](../stack/cache-redis.md), [Langfuse](../stack/tracing-langfuse.md)
- Cross-cutting: [Auth](../cross-cutting/auth-jwt.md), [Logging](../cross-cutting/logging-structured.md), [Observability](../cross-cutting/observability.md), [Rate limiting](../cross-cutting/rate-limiting.md)

## What it does

An operations crew of three specialist agents — DevOps, Security, and Database — that analyze an infrastructure request or incident report from their respective perspectives. Each agent works independently with its own tools, and their findings are aggregated into a unified ops report.

This implements **independent flat execution** — agents work in parallel on the same input, producing independent analyses that are merged at the end.

## Architecture

```
Input (incident / infra request)
    |
    v
┌──────────────────────────────────────┐
│            CrewAI Crew               │
│                                      │
│   ┌──────────┐  ┌──────────┐  ┌─────────┐
│   │  DevOps  │  │ Security │  │Database │
│   │  Agent   │  │  Agent   │  │ Agent   │
│   │          │  │          │  │         │
│   │ tools:   │  │ tools:   │  │ tools:  │
│   │ - k8s    │  │ - vuln   │  │ - query │
│   │   status │  │   scan   │  │   perf  │
│   │ - logs   │  │ - audit  │  │ - schema│
│   └────┬─────┘  └────┬─────┘  └────┬────┘
│        │             │             │     │
│        v             v             v     │
│   ┌──────────────────────────────────┐   │
│   │         Aggregation              │   │
│   └──────────────────────────────────┘   │
└──────────────────────────────────────────┘
    |
    v
Unified ops report
```

## Data Models

### Python (Pydantic)

```python
from enum import Enum
from pydantic import BaseModel, Field


class Priority(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class OpsRequest(BaseModel):
    description: str = Field(..., min_length=1, description="Incident description or infrastructure request")
    context: dict | None = Field(default=None, description="Optional context: affected services, timestamps, etc.")


class AgentFinding(BaseModel):
    """Output from a single specialist agent."""
    agent_name: str = Field(..., description="devops, security, or database")
    summary: str = Field(..., description="One-paragraph summary of findings")
    recommendations: list[str] = Field(default_factory=list, description="Actionable recommendations")
    severity: Priority
    details: str | None = Field(default=None, description="Extended analysis if needed")


class OpsReport(BaseModel):
    """Aggregated report from all agents."""
    findings: dict[str, AgentFinding] = Field(..., description="Keyed by agent name")
    priority: Priority = Field(..., description="Overall incident priority (highest of all agents)")
    summary: str = Field(..., description="Executive summary combining all perspectives")
    trace_id: str
```

### TypeScript (Zod)

```typescript
import { z } from "zod";

export const Priority = z.enum(["critical", "high", "medium", "low"]);
export type Priority = z.infer<typeof Priority>;

export const OpsRequest = z.object({
  description: z.string().min(1),
  context: z.record(z.unknown()).optional(),
});
export type OpsRequest = z.infer<typeof OpsRequest>;

export const AgentFinding = z.object({
  agent_name: z.string(),
  summary: z.string(),
  recommendations: z.array(z.string()).default([]),
  severity: Priority,
  details: z.string().optional(),
});
export type AgentFinding = z.infer<typeof AgentFinding>;

export const OpsReport = z.object({
  findings: z.record(AgentFinding),
  priority: Priority,
  summary: z.string(),
  trace_id: z.string(),
});
export type OpsReport = z.infer<typeof OpsReport>;
```

## API Contract

### `POST /ops`

Run the ops crew on an incident or infrastructure request.

**Request:**

```json
{
  "description": "API latency increased 3x in the last hour, p99 is at 2.5s",
  "context": {
    "affected_services": ["api-gateway", "user-service"],
    "started_at": "2026-05-01T01:30:00Z"
  }
}
```

**Response (200):**

```json
{
  "findings": {
    "devops": {
      "agent_name": "devops",
      "summary": "Pod memory usage at 85%, approaching OOM threshold. HPA not triggering due to CPU-based scaling.",
      "recommendations": ["Switch to memory-based HPA scaling", "Increase pod memory limits"],
      "severity": "high"
    },
    "security": {
      "agent_name": "security",
      "summary": "No security incidents detected. Rate limiting is active and within normal bounds.",
      "recommendations": [],
      "severity": "low"
    },
    "database": {
      "agent_name": "database",
      "summary": "Slow query detected: full table scan on users table due to missing index on created_at.",
      "recommendations": ["Add index on users.created_at", "Enable query plan caching"],
      "severity": "high"
    }
  },
  "priority": "high",
  "summary": "Latency spike caused by combination of high memory pressure (DevOps) and slow DB queries (Database). No security concerns.",
  "trace_id": "b2c3d4e5-f6a7-8901-bcde-f23456789012"
}
```

**Errors:**

| Status | Body | When |
|--------|------|------|
| 400 | `{"error": "Invalid request", "details": [...]}` | Empty description |
| 500 | `{"error": "Crew execution failed", "partial_findings": {...}}` | One or more agents failed |

### `GET /health`

Returns `{"status": "ok"}`.

## Tool Specifications

### DevOps Agent Tools

#### `check_k8s_status`

| Field | Value |
|-------|-------|
| **Description** | Check Kubernetes cluster and pod status for specified services. |
| **Parameter** | `services` (list[string], optional) — Service names to check. If empty, checks all. |
| **Return type** | `string` — Pod status, resource usage, HPA state, recent restarts. |

#### `query_logs`

| Field | Value |
|-------|-------|
| **Description** | Search application and infrastructure logs for errors and anomalies. |
| **Parameters** | `service` (string, required) — Service name. `timeframe` (string, optional) — e.g., "1h", "30m". Default "1h". |
| **Return type** | `string` — Relevant log entries with timestamps. |

### Security Agent Tools

#### `scan_vulnerabilities`

| Field | Value |
|-------|-------|
| **Description** | Scan for known vulnerabilities, unusual access patterns, or security misconfigurations. |
| **Parameter** | `target` (string, required) — Service or component to scan. |
| **Return type** | `string` — Vulnerability findings with CVE references where applicable. |

#### `check_audit_log`

| Field | Value |
|-------|-------|
| **Description** | Review security audit logs for suspicious activity. |
| **Parameters** | `timeframe` (string, optional) — Default "1h". `event_types` (list[string], optional) — e.g., ["auth_failure", "privilege_escalation"]. |
| **Return type** | `string` — Audit events matching the criteria. |

### Database Agent Tools

#### `check_query_performance`

| Field | Value |
|-------|-------|
| **Description** | Analyze slow queries, lock contention, and connection pool usage. |
| **Parameter** | `threshold_ms` (int, optional) — Minimum query duration to flag. Default 1000. |
| **Return type** | `string` — Slow queries with execution plans and timing. |

#### `check_schema_health`

| Field | Value |
|-------|-------|
| **Description** | Check for missing indexes, table bloat, and schema issues. |
| **Parameter** | `tables` (list[string], optional) — Specific tables to check. If empty, checks all. |
| **Return type** | `string` — Index coverage, table sizes, bloat estimates. |

## Prompt Specifications

### DevOps Agent (CrewAI role/goal/backstory)

```python
Agent(
    role="Senior DevOps Engineer",
    goal="Diagnose infrastructure issues and recommend operational fixes",
    backstory="""You are a senior DevOps engineer with 10 years of experience
    managing Kubernetes clusters, CI/CD pipelines, and cloud infrastructure.
    You think in terms of resource utilization, scaling policies, and deployment
    health. When you see a problem, you immediately check pod status, resource
    usage, and recent deployments.""",
    tools=[check_k8s_status, query_logs],
)
```

### Security Agent

```python
Agent(
    role="Security Engineer",
    goal="Identify security threats, vulnerabilities, and suspicious activity",
    backstory="""You are a security engineer specializing in application and
    infrastructure security. You think in terms of attack vectors, access
    patterns, and compliance. You always check for unauthorized access,
    vulnerability exposure, and security misconfigurations before concluding
    an incident is non-security-related.""",
    tools=[scan_vulnerabilities, check_audit_log],
)
```

### Database Agent

```python
Agent(
    role="Database Reliability Engineer",
    goal="Diagnose database performance issues and recommend optimizations",
    backstory="""You are a database reliability engineer who specializes in
    PostgreSQL performance tuning. You think in terms of query plans, index
    coverage, connection pools, and lock contention. When latency increases,
    your first instinct is to check for slow queries and missing indexes.""",
    tools=[check_query_performance, check_schema_health],
)
```

**Design rationale:** CrewAI's backstory mechanism shapes each agent's reasoning style. The DevOps agent "thinks in terms of resource utilization," the Security agent "thinks in terms of attack vectors," and the Database agent "thinks in terms of query plans." This creates genuinely different analytical perspectives on the same incident.

### TypeScript equivalent

In the TypeScript track (no CrewAI), each agent is a separate `generateText()` call with the role description embedded in the system prompt:

```typescript
const devopsResult = await generateText({
  model: anthropic(config.agentModel),
  system: `You are a Senior DevOps Engineer. ${backstory}`,
  prompt: `Analyze this incident from a DevOps perspective:\n${description}`,
  tools: { check_k8s_status, query_logs },
  maxSteps: 3,
});
```

All three calls run via `Promise.all()` for parallel execution.

## Key files

### Python track

| File | Role |
|------|------|
| `app/main.py` | FastAPI entrypoint with lifespan, routers, health check |
| `app/settings.py` | Config: model name, tool endpoints |
| `app/models/schemas.py` | All Pydantic models: `OpsRequest`, `AgentFinding`, `OpsReport` |
| `app/agent/crew.py` | CrewAI crew definition: agents, tasks, parallel process |
| `app/agent/devops.py` | DevOps agent — role, goal, backstory, tools |
| `app/agent/security.py` | Security agent — vulnerability scanning focus |
| `app/agent/database.py` | Database agent — performance and schema focus |
| `app/tools/k8s.py` | Kubernetes cluster status tool (mock for local dev) |
| `app/tools/vuln_scan.py` | Vulnerability scanner tool (mock for local dev) |
| `app/tools/db_perf.py` | Database performance query tool (mock for local dev) |
| `app/api/ops.py` | `/ops` endpoint — runs crew, returns unified report |

### TypeScript track

| File | Role |
|------|------|
| `src/index.ts` | Hono entrypoint with routes and health check |
| `src/config.ts` | Zod-validated env config |
| `src/schemas/index.ts` | All Zod schemas |
| `src/agent/crew.ts` | Orchestrator: `Promise.all()` over 3 agent calls + aggregation |
| `src/agent/devops.ts` | DevOps agent: `generateText()` with k8s/log tools |
| `src/agent/security.ts` | Security agent: `generateText()` with vuln/audit tools |
| `src/agent/database.ts` | Database agent: `generateText()` with perf/schema tools |
| `src/tools/k8s.ts` | Kubernetes status tool |
| `src/tools/vuln-scan.ts` | Vulnerability scanner tool |
| `src/tools/db-perf.ts` | Database performance tool |
| `src/api/ops.ts` | `/ops` route handler |

## Implementation Roadmap

| Step | Task | Key deliverables |
|------|------|-----------------|
| 1 | **Project scaffolding** | FastAPI/Hono app with `/health`, settings, structured logging |
| 2 | **Data models** | All Pydantic + Zod schemas for request, findings, report |
| 3 | **Mock tools** | All 6 tools with mock responses for local dev |
| 4 | **DevOps agent** | CrewAI Agent with role/goal/backstory + k8s/log tools |
| 5 | **Security agent** | CrewAI Agent with vuln/audit tools |
| 6 | **Database agent** | CrewAI Agent with perf/schema tools |
| 7 | **Crew assembly** | CrewAI Crew with parallel process, task definitions |
| 8 | **Aggregation** | Merge agent findings, compute overall priority, generate summary |
| 9 | **API endpoint** | `POST /ops` wired to crew, trace ID generation |
| 10 | **Cross-cutting** | JWT auth, rate limiting, Langfuse tracing per agent |
| 11 | **Unit tests** | Schema validation, individual agent mocks, aggregation logic |
| 12 | **Integration + eval** | End-to-end crew run with real LLM, promptfoo security scan |

## Environment & Deployment

### Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `AGENT_MODEL` | No | `claude-sonnet-4-6-20250514` | Model for all three agents |
| `DATABASE_URL` | No | `postgresql+asyncpg://agent:agent@localhost:5432/agent_db` | Postgres connection |
| `REDIS_URL` | No | `redis://localhost:6379` | Redis for rate limiting |
| `LANGFUSE_PUBLIC_KEY` | No | `pk-lf-local` | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | No | `sk-lf-local` | Langfuse secret key |
| `LANGFUSE_HOST` | No | `http://localhost:3000` | Langfuse server URL |
| `JWT_SECRET` | No | `change-me-in-production` | JWT signing secret |
| `APP_ENV` | No | `development` | Environment name |
| `LOG_LEVEL` | No | `INFO` | Log level |

### Docker Compose

See [Docker Compose template](../reference/docker-compose-template.md) for base infrastructure. This agent needs: Postgres, Redis, Langfuse. No Qdrant required.

## Test Strategy

### Unit tests

```python
def test_ops_report_priority_is_highest():
    """Overall priority should be the highest severity across all agents."""
    report = aggregate_findings([
        AgentFinding(agent_name="devops", summary="ok", severity="low", recommendations=[]),
        AgentFinding(agent_name="security", summary="issue", severity="critical", recommendations=["fix"]),
        AgentFinding(agent_name="database", summary="ok", severity="low", recommendations=[]),
    ])
    assert report.priority == "critical"

def test_partial_failure_still_returns_findings():
    """If one agent fails, the other two findings are still included."""
    # Mock security agent to raise, devops and database succeed
    # Assert report has 2 findings, not 3
```

### Integration tests (main branch only)

```python
async def test_crew_produces_three_findings():
    """End-to-end: all 3 agents should produce findings for a real incident."""
    response = await client.post("/ops", json={
        "description": "API response times doubled in the last 30 minutes",
    })
    assert response.status_code == 200
    data = response.json()
    assert "devops" in data["findings"]
    assert "security" in data["findings"]
    assert "database" in data["findings"]
```

### Eval assertions

- All 3 agents produce non-empty findings for a latency incident
- DevOps agent mentions infrastructure/scaling in its summary
- Database agent mentions queries/indexes in its summary
- Security agent correctly identifies "no security concern" for non-security incidents

## Eval Dataset

```jsonl
{"input": {"description": "API latency increased 3x in the last hour, p99 is at 2.5s"}, "expected_priority": "high", "expected_agents": ["devops", "security", "database"]}
{"input": {"description": "Unauthorized access attempts detected from 3 IPs in the last 10 minutes"}, "expected_priority": "critical", "expected_agents": ["devops", "security", "database"]}
{"input": {"description": "Database connection pool exhausted, new connections timing out"}, "expected_priority": "critical", "expected_agents": ["devops", "security", "database"]}
{"input": {"description": "Deployment rollback needed — new version causing 500 errors on /api/users"}, "expected_priority": "high", "expected_agents": ["devops", "security", "database"]}
{"input": {"description": "Disk usage on primary DB server at 92%, growing 2% per day"}, "expected_priority": "medium", "expected_agents": ["devops", "security", "database"]}
{"input": {"description": "SSL certificate expiring in 3 days for api.example.com"}, "expected_priority": "high", "expected_agents": ["devops", "security", "database"]}
```

## Design decisions

- **CrewAI for flat collaboration:** The Crew/Agent/Task model is purpose-built for this. Three agents with distinct roles working on the same input is CrewAI's sweet spot.
- **Parallel execution:** Agents analyze independently — no need for one to wait on another. CrewAI supports parallel task execution.
- **Role-based personas:** CrewAI's backstory + role + goal gives each agent a strong persona without complex prompt engineering. The DevOps agent thinks in terms of infrastructure; the Security agent thinks in terms of threats.
- **Aggregation as a final step:** Individual agent outputs are merged into a structured `OpsReport` with per-agent findings and a unified priority level.
- **Mock tools for local dev:** All infrastructure tools (k8s status, vuln scan, db perf) have mock implementations. This lets you develop and test the agent logic without real infrastructure.
