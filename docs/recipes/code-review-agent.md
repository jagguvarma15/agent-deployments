# Recipe: Code Review Agent

**Status:** Blueprint (design spec)

**Composes:**

- Pattern: [Plan, Execute, Reflect](../patterns/plan-execute-reflect.md)
- Framework (Py): [LangGraph](../frameworks/langgraph.md) (state graph with planner/executor/reflector nodes)
- Framework (TS): [Vercel AI SDK](../frameworks/vercel-ai-sdk.md) (manual orchestration)
- Stack: [FastAPI](../stack/api-fastapi.md) / [Hono](../stack/api-hono.md), [Postgres](../stack/relational-postgres.md), [Redis](../stack/cache-redis.md), [Langfuse](../stack/tracing-langfuse.md)
- Cross-cutting: [Auth](../cross-cutting/auth-jwt.md), [Logging](../cross-cutting/logging-structured.md), [Observability](../cross-cutting/observability.md), [Rate limiting](../cross-cutting/rate-limiting.md)

## Load as Context

Feed these files to your AI coding assistant to build this agent:

**Core (always load):**
- `docs/recipes/code-review-agent.md` — this blueprint
- `docs/patterns/plan-execute-reflect.md` — the plan-execute-reflect pattern
- `docs/frameworks/langgraph.md` (Python) or `docs/frameworks/vercel-ai-sdk.md` (TypeScript)
- `docs/stack/llm-claude.md` — LLM integration and model selection

**Stack (load for Tier 2 — API-ready):**
- `docs/stack/api-fastapi.md` or `docs/stack/api-hono.md` — API layer
- `docs/stack/relational-postgres.md` — review result persistence
- `docs/stack/cache-redis.md` — rate limiting backend

**Production concerns (load for Tier 3):**
- `docs/cross-cutting/auth-jwt.md` · `docs/cross-cutting/rate-limiting.md` · `docs/cross-cutting/logging-structured.md` · `docs/cross-cutting/observability.md` · `docs/cross-cutting/testing-strategy.md`

**Scaffolding:** `docs/reference/docker-templates.md` · `docs/reference/docker-compose-template.md`

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

## Data Models

### Python (Pydantic)

```python
from enum import Enum
from pydantic import BaseModel, Field


class Severity(str, Enum):
    critical = "critical"
    warning = "warning"
    info = "info"
    nitpick = "nitpick"


class Category(str, Enum):
    security = "security"
    correctness = "correctness"
    performance = "performance"
    style = "style"
    testing = "testing"


class ReviewRequest(BaseModel):
    diff: str = Field(..., min_length=1, description="Unified diff or PR content to review")
    focus_areas: list[Category] | None = Field(default=None, description="Optional: limit review to specific categories")
    max_replanning_rounds: int = Field(default=2, ge=0, le=5)


class ReviewStep(BaseModel):
    """A single planned review step."""
    description: str = Field(..., description="What to check")
    category: Category
    target_lines: list[int] | None = Field(default=None, description="Specific line numbers to examine")


class ReviewPlan(BaseModel):
    steps: list[ReviewStep] = Field(..., min_length=1)
    rationale: str = Field(..., description="Why these steps were chosen")


class Finding(BaseModel):
    severity: Severity
    category: Category
    line: int | None = Field(default=None, description="Line number in the diff")
    file_path: str | None = None
    issue: str = Field(..., description="Description of the issue found")
    suggestion: str = Field(..., description="Recommended fix")
    code_snippet: str | None = Field(default=None, description="Relevant code")


class ReflectionResult(BaseModel):
    finding_quality: str = Field(..., description="Assessment: substantive, superficial, or false_positive")
    needs_deeper_look: bool
    additional_steps: list[ReviewStep] | None = None
    reasoning: str


class ReviewReport(BaseModel):
    findings: list[Finding]
    plan_steps_executed: int
    replanning_rounds: int
    summary: str = Field(..., description="High-level review summary")
    trace_id: str
```

### TypeScript (Zod)

```typescript
import { z } from "zod";

export const Severity = z.enum(["critical", "warning", "info", "nitpick"]);
export type Severity = z.infer<typeof Severity>;

export const Category = z.enum(["security", "correctness", "performance", "style", "testing"]);
export type Category = z.infer<typeof Category>;

export const ReviewRequest = z.object({
  diff: z.string().min(1),
  focus_areas: z.array(Category).optional(),
  max_replanning_rounds: z.number().min(0).max(5).default(2),
});
export type ReviewRequest = z.infer<typeof ReviewRequest>;

export const ReviewStep = z.object({
  description: z.string(),
  category: Category,
  target_lines: z.array(z.number()).optional(),
});

export const ReviewPlan = z.object({
  steps: z.array(ReviewStep).min(1),
  rationale: z.string(),
});
export type ReviewPlan = z.infer<typeof ReviewPlan>;

export const Finding = z.object({
  severity: Severity,
  category: Category,
  line: z.number().optional(),
  file_path: z.string().optional(),
  issue: z.string(),
  suggestion: z.string(),
  code_snippet: z.string().optional(),
});
export type Finding = z.infer<typeof Finding>;

export const ReflectionResult = z.object({
  finding_quality: z.string(),
  needs_deeper_look: z.boolean(),
  additional_steps: z.array(ReviewStep).optional(),
  reasoning: z.string(),
});

export const ReviewReport = z.object({
  findings: z.array(Finding),
  plan_steps_executed: z.number(),
  replanning_rounds: z.number(),
  summary: z.string(),
  trace_id: z.string(),
});
export type ReviewReport = z.infer<typeof ReviewReport>;
```

### LangGraph State (TypedDict)

```python
from typing import TypedDict

class ReviewState(TypedDict):
    diff: str
    focus_areas: list[str] | None
    plan: ReviewPlan | None
    current_step_index: int
    findings: list[Finding]
    reflection_history: list[ReflectionResult]
    replanning_count: int
    max_replanning: int
    status: str  # "planning", "executing", "reflecting", "aggregating", "done"
```

## API Contract

### `POST /review`

Submit a diff for code review.

**Request:**

```json
{
  "diff": "--- a/app.py\n+++ b/app.py\n@@ -10,6 +10,7 @@\n+    query = f\"SELECT * FROM users WHERE id={user_id}\"",
  "focus_areas": ["security", "correctness"],
  "max_replanning_rounds": 2
}
```

**Response (200):**

```json
{
  "findings": [
    {
      "severity": "critical",
      "category": "security",
      "line": 5,
      "file_path": "app.py",
      "issue": "SQL injection vulnerability — user_id is interpolated directly into query string",
      "suggestion": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id=%s', (user_id,))",
      "code_snippet": "query = f\"SELECT * FROM users WHERE id={user_id}\""
    }
  ],
  "plan_steps_executed": 4,
  "replanning_rounds": 0,
  "summary": "Found 1 critical security issue (SQL injection). No correctness or style issues detected.",
  "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Errors:**

| Status | Body | When |
|--------|------|------|
| 400 | `{"error": "Invalid request", "details": [...]}` | Empty diff or invalid focus_areas |
| 422 | `{"error": "Review failed", "partial_findings": [...]}` | Agent error mid-review |
| 500 | `{"error": "Internal error"}` | LLM or graph execution failure |

### `GET /health`

Returns `{"status": "ok"}`.

## Tool Specifications

### `parse_diff`

| Field | Value |
|-------|-------|
| **Description** | Parse a unified diff into structured file-level changes with line numbers and change types. |
| **Parameter** | `diff` (string, required) — Raw unified diff text. |
| **Return type** | `string` — JSON-formatted list of file changes with added/removed/modified lines. |

**Example output:**

```json
[
  {
    "file": "app.py",
    "changes": [
      {"line": 13, "type": "added", "content": "    query = f\"SELECT * FROM users WHERE id={user_id}\""}
    ]
  }
]
```

### `analyze_code`

| Field | Value |
|-------|-------|
| **Description** | Analyze a code snippet for issues in a specific category (security, performance, etc.). |
| **Parameters** | `code` (string, required) — Code to analyze. `category` (string, required) — Review category. |
| **Return type** | `string` — Analysis findings as structured text. |

### `suggest_fix`

| Field | Value |
|-------|-------|
| **Description** | Generate a concrete fix suggestion for a finding, including corrected code. |
| **Parameters** | `code` (string, required) — Original code. `issue` (string, required) — Description of the problem. |
| **Return type** | `string` — Suggested replacement code with explanation. |

## Prompt Specifications

### Planner

```
You are a code review planner. Given a diff, create a targeted review plan.

Analyze the diff and identify what needs to be reviewed. Consider:
- Security: injection, auth bypass, data exposure, unsafe deserialization
- Correctness: logic errors, off-by-one, null/undefined handling, race conditions
- Performance: N+1 queries, unnecessary allocations, missing indexes
- Style: naming conventions, dead code, overly complex logic
- Testing: untested edge cases, missing error path tests

{focus_areas_instruction}

For each review step, specify:
1. What to check (be specific — reference file names and line numbers)
2. Which category it falls under
3. Which lines to examine

Prioritize security and correctness over style.
```

**Design rationale:** The planner sees the raw diff and produces a checklist. By listing specific vulnerability classes (injection, auth bypass, etc.), the prompt steers the planner toward concrete checks rather than vague "look for issues."

### Executor

```
You are a code review executor. Perform one specific review step on the given diff.

Diff:
{diff}

Review step: {step_description}
Category: {step_category}
Target lines: {target_lines}

Analyze the code carefully. For each issue found:
1. State the severity (critical, warning, info, nitpick)
2. Reference the exact line number
3. Explain the issue clearly
4. Provide a concrete fix with corrected code

If the code is clean for this check, say so explicitly — do not invent findings.
```

**Design rationale:** "Do not invent findings" is critical — without it, the executor hallucinates issues to appear thorough. The explicit severity scale prevents everything from being labeled "critical."

### Reflector

```
You are a code review quality assessor. Evaluate whether a finding is substantive.

Finding:
{finding_json}

Diff context:
{relevant_diff_lines}

Assess:
1. Is this finding substantive, superficial, or a false positive?
2. Does this area need deeper investigation?
3. Are there related issues the executor might have missed?

If deeper investigation is needed, propose additional review steps.
Be honest — it's better to flag a superficial finding than to let it pass.
```

**Design rationale:** The reflector acts as a quality gate. Without it, the executor produces a mix of real issues and noise. The reflector prunes false positives and requests re-execution when findings are shallow.

## Key files

### Python track

| File | Role |
|------|------|
| `app/main.py` | FastAPI entrypoint with lifespan, routers, health check |
| `app/settings.py` | Config: model names, max replanning rounds |
| `app/models/schemas.py` | All Pydantic models and LangGraph state TypedDict |
| `app/agent/graph.py` | LangGraph state graph: planner → executor → reflector → aggregator |
| `app/agent/planner.py` | Planner node — analyzes diff, produces review checklist |
| `app/agent/executor.py` | Executor node — runs one review step, produces findings |
| `app/agent/reflector.py` | Reflector node — evaluates finding quality, decides continue/replan |
| `app/tools/diff_parser.py` | Parses unified diff into structured file changes |
| `app/api/review.py` | `/review` endpoint — accepts diff, returns structured review |

### TypeScript track

| File | Role |
|------|------|
| `src/index.ts` | Hono entrypoint with routes and health check |
| `src/config.ts` | Zod-validated env config |
| `src/schemas/index.ts` | All Zod schemas |
| `src/agent/review-loop.ts` | Manual plan-execute-reflect loop using `generateObject` |
| `src/agent/planner.ts` | Planner: `generateObject({ schema: ReviewPlan })` |
| `src/agent/executor.ts` | Executor: `generateObject({ schema: Finding })` per step |
| `src/agent/reflector.ts` | Reflector: `generateObject({ schema: ReflectionResult })` |
| `src/tools/diff-parser.ts` | Diff parsing utility |
| `src/api/review.ts` | `/review` route handler |

## Implementation Roadmap

| Step | Task | Key deliverables |
|------|------|-----------------|
| 1 | **Project scaffolding** | FastAPI/Hono app with `/health`, settings, structured logging |
| 2 | **Data models** | All Pydantic + Zod schemas, LangGraph state TypedDict |
| 3 | **Diff parser tool** | Parse unified diff into file-level changes with line numbers |
| 4 | **Planner node** | Agent that analyzes diff and produces `ReviewPlan` |
| 5 | **Executor node** | Agent that runs one step, produces `Finding` list |
| 6 | **Reflector node** | Agent that evaluates finding quality, proposes re-planning |
| 7 | **LangGraph wiring** | State graph with conditional edges: reflector → continue / replan |
| 8 | **Aggregator** | Collects findings, deduplicates, generates summary |
| 9 | **API endpoint** | `POST /review` wired to graph, trace ID generation |
| 10 | **Cross-cutting** | JWT auth, rate limiting, Langfuse tracing per node |
| 11 | **Unit tests** | Diff parser, schema validation, graph with mocked LLM |
| 12 | **Integration + eval** | End-to-end review with real LLM, promptfoo security scan |

## Environment & Deployment

### Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `PLANNER_MODEL` | No | `claude-sonnet-4-6-20250514` | Model for planning |
| `EXECUTOR_MODEL` | No | `claude-sonnet-4-6-20250514` | Model for execution |
| `REFLECTOR_MODEL` | No | `claude-haiku-4-5-20251001` | Model for reflection (cheaper, fast) |
| `MAX_REPLANNING_ROUNDS` | No | `2` | Max re-planning iterations |
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

### Infrastructure dependencies

| Component | Required? | Why |
|-----------|-----------|-----|
| Postgres | Yes | Review results and finding persistence |
| Redis | Yes | Rate limiting backend |
| Qdrant | No | Not needed — this agent analyzes diffs, not documents |
| Langfuse | Recommended | Plan/execute/reflect step tracing (skip for local dev) |

## Test Strategy

### Unit tests

```python
def test_diff_parser_single_file():
    """Parses a simple single-file diff into structured changes."""
    diff = "--- a/app.py\n+++ b/app.py\n@@ -1,3 +1,4 @@\n import os\n+import sys\n"
    result = parse_diff(diff)
    assert len(result) == 1
    assert result[0]["file"] == "app.py"
    assert result[0]["changes"][0]["type"] == "added"

def test_review_plan_requires_steps():
    """ReviewPlan must have at least one step."""
    with pytest.raises(ValidationError):
        ReviewPlan(steps=[], rationale="nothing to do")

def test_reflector_limits_replanning(mock_llm_client):
    """Reflector stops requesting re-plans after max_replanning_rounds."""
    # Set max_replanning=2, simulate 2 re-plans
    # Assert third reflection does NOT trigger re-plan
```

### Integration tests (main branch only)

```python
async def test_review_detects_sql_injection():
    """End-to-end: diff with SQL injection should produce critical finding."""
    response = await client.post("/review", json={
        "diff": "--- a/db.py\n+++ b/db.py\n@@ -5,6 +5,7 @@\n+    q = f\"SELECT * FROM users WHERE id={uid}\"",
    })
    assert response.status_code == 200
    findings = response.json()["findings"]
    assert any(f["severity"] == "critical" and f["category"] == "security" for f in findings)
```

### Eval assertions

- Known SQL injection diff → at least 1 critical security finding
- Clean diff (only whitespace changes) → 0 critical/warning findings
- Reflector prunes false positives (fabricated issues don't appear in final report)
- Replanning count never exceeds `max_replanning_rounds`

## Eval Dataset

```jsonl
{"input": {"diff": "--- a/db.py\n+++ b/db.py\n@@ -5,6 +5,7 @@\n+    q = f\"SELECT * FROM users WHERE id={uid}\""}, "expected_severity": "critical", "expected_category": "security"}
{"input": {"diff": "--- a/auth.py\n+++ b/auth.py\n@@ -12,6 +12,7 @@\n+    if password == stored_password:"}, "expected_severity": "critical", "expected_category": "security"}
{"input": {"diff": "--- a/api.py\n+++ b/api.py\n@@ -8,6 +8,7 @@\n+    return jsonify(user.__dict__)"}, "expected_severity": "warning", "expected_category": "security"}
{"input": {"diff": "--- a/utils.py\n+++ b/utils.py\n@@ -1,3 +1,4 @@\n+    for item in items:\n+        result = db.query(Item).filter_by(id=item.id).first()"}, "expected_severity": "warning", "expected_category": "performance"}
{"input": {"diff": "--- a/app.py\n+++ b/app.py\n@@ -1,3 +1,4 @@\n import os\n+import sys\n"}, "expected_severity": null, "expected_category": null}
{"input": {"diff": "--- a/handler.py\n+++ b/handler.py\n@@ -20,6 +20,8 @@\n+    try:\n+        result = process(data)\n+    except:\n+        pass"}, "expected_severity": "warning", "expected_category": "correctness"}
```

## Design decisions

- **LangGraph for state management:** The plan evolves during execution (reflection may trigger re-planning). LangGraph's TypedDict state and conditional edges handle this naturally. Checkpointing enables resuming long reviews.
- **Structured review output:** Each finding has severity, category, line reference, issue description, and suggestion. This makes reviews actionable, not just commentary.
- **Reflector as quality gate:** After each review step, the reflector evaluates whether the finding is substantive or superficial. This prevents the agent from producing vague "looks good" reviews.
- **Max replanning budget:** Reflection can trigger re-planning up to 2 times. Prevents infinite review loops on complex diffs.
- **Separate models per node:** The reflector can use a cheaper model (Haiku) since it's making binary quality judgments, while the executor needs a more capable model for nuanced code analysis.
