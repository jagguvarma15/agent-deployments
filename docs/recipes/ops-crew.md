# Recipe: Ops Crew

**Status:** Skeleton (design intent)

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

## Intended key files

### Python track

| File | Role |
|------|------|
| `app/agent/crew.py` | CrewAI crew definition: agents, tasks, process |
| `app/agent/devops.py` | DevOps agent — role, goal, backstory, tools |
| `app/agent/security.py` | Security agent — vulnerability scanning focus |
| `app/agent/database.py` | Database agent — performance and schema focus |
| `app/tools/k8s.py` | Kubernetes cluster status tool |
| `app/tools/vuln_scan.py` | Vulnerability scanner tool |
| `app/tools/db_perf.py` | Database performance query tool |
| `app/models/schemas.py` | `OpsReport`, `AgentFinding` schemas |
| `app/api/ops.py` | `/ops` endpoint — runs crew, returns unified report |

## Example interaction

```bash
curl -X POST http://localhost:8000/ops \
  -H "Content-Type: application/json" \
  -d '{"description": "API latency increased 3x in the last hour, p99 is at 2.5s"}'
```

Expected response:

```json
{
  "findings": {
    "devops": {
      "summary": "Pod memory usage at 85%, approaching OOM threshold. HPA not triggering due to CPU-based scaling.",
      "recommendations": ["Switch to memory-based HPA scaling", "Increase pod memory limits"]
    },
    "security": {
      "summary": "No security incidents detected. Rate limiting is active and within normal bounds.",
      "recommendations": []
    },
    "database": {
      "summary": "Slow query detected: full table scan on users table due to missing index on created_at.",
      "recommendations": ["Add index on users.created_at", "Enable query plan caching"]
    }
  },
  "priority": "high",
  "trace_id": "..."
}
```

## Design intent

- **CrewAI for flat collaboration:** The Crew/Agent/Task model is purpose-built for this. Three agents with distinct roles working on the same input is CrewAI's sweet spot.
- **Parallel execution:** Agents analyze independently — no need for one to wait on another. CrewAI supports parallel task execution.
- **Role-based personas:** CrewAI's backstory + role + goal gives each agent a strong persona without complex prompt engineering. The DevOps agent thinks in terms of infrastructure; the Security agent thinks in terms of threats.
- **Aggregation as a final step:** Individual agent outputs are merged into a structured `OpsReport` with per-agent findings and a unified priority level.
