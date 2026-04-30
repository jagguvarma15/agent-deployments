# Recipe: Code Review Agent

**Status:** Skeleton (design intent)

**Composes:**

- Pattern: [Plan, Execute, Reflect](../patterns/plan-execute-reflect.md)
- Framework (Py): [LangGraph](../frameworks/langgraph.md) (state graph with planner/executor/reflector nodes)
- Framework (TS): [Vercel AI SDK](../frameworks/vercel-ai-sdk.md) (manual orchestration)
- Stack: [FastAPI](../stack/api-fastapi.md) / [Hono](../stack/api-hono.md), [Postgres](../stack/relational-postgres.md), [Redis](../stack/cache-redis.md), [Langfuse](../stack/tracing-langfuse.md)
- Cross-cutting: [Auth](../cross-cutting/auth-jwt.md), [Logging](../cross-cutting/logging-structured.md), [Observability](../cross-cutting/observability.md), [Rate limiting](../cross-cutting/rate-limiting.md)

## What it does

A code review agent that takes a diff or PR, plans what to review (security, correctness, style, performance), executes each review step with targeted analysis, then reflects on whether the review is complete or needs deeper investigation. Produces a structured review with findings, severity levels, and suggested fixes.

This implements **Plan-Execute-Reflect** — the planner creates a review checklist, the executor analyzes each area, and the reflector decides if the review is thorough enough or if re-planning is needed.

## Architecture

```
Input (diff / PR URL)
    |
    v
┌──────────────────────────────────────────┐
│              LangGraph State             │
│                                          │
│   [Planner] ──> review_plan: [          │
│       "Check for SQL injection",         │
│       "Verify error handling",           │
│       "Check type safety",               │
│       "Review test coverage"             │
│   ]                                      │
│       │                                  │
│       v                                  │
│   [Executor] ──> execute step 1 ──> finding │
│       │                                  │
│       v                                  │
│   [Reflector] ──> "step passed" or       │
│       │           "needs deeper look"    │
│       │                                  │
│       ├──> continue to step 2            │
│       └──> [Re-planner] ──> revised steps │
│                                          │
│       ... (repeat until all steps done)  │
│       │                                  │
│       v                                  │
│   [Aggregator] ──> structured review     │
└──────────────────────────────────────────┘
    |
    v
Review report
```

## Intended key files

### Python track

| File | Role |
|------|------|
| `app/agent/graph.py` | LangGraph state graph: planner → executor → reflector → aggregator |
| `app/agent/planner.py` | Planner node — analyzes diff, produces review checklist |
| `app/agent/executor.py` | Executor node — runs one review step, produces findings |
| `app/agent/reflector.py` | Reflector node — evaluates finding quality, decides continue/replan |
| `app/models/schemas.py` | `ReviewPlan`, `ReviewStep`, `Finding`, `ReviewReport` schemas |
| `app/tools/diff_parser.py` | Parses diff/PR into reviewable chunks |
| `app/api/review.py` | `/review` endpoint — accepts diff, returns structured review |

## Example interaction

```bash
curl -X POST http://localhost:8000/review \
  -H "Content-Type: application/json" \
  -d '{"diff": "--- a/app.py\n+++ b/app.py\n@@ ...\n+    query = f\"SELECT * FROM users WHERE id={user_id}\""}'
```

Expected response:

```json
{
  "findings": [
    {
      "severity": "critical",
      "category": "security",
      "line": 5,
      "issue": "SQL injection vulnerability — user_id is interpolated directly into query string",
      "suggestion": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id=%s', (user_id,))"
    }
  ],
  "plan_steps_executed": 4,
  "replanning_rounds": 0,
  "trace_id": "..."
}
```

## Design intent

- **LangGraph for state management:** The plan evolves during execution (reflection may trigger re-planning). LangGraph's TypedDict state and conditional edges handle this naturally. Checkpointing enables resuming long reviews.
- **Structured review output:** Each finding has severity, category, line reference, issue description, and suggestion. This makes reviews actionable, not just commentary.
- **Reflector as quality gate:** After each review step, the reflector evaluates whether the finding is substantive or superficial. This prevents the agent from producing vague "looks good" reviews.
- **Max replanning budget:** Reflection can trigger re-planning up to 2 times. Prevents infinite review loops on complex diffs.
