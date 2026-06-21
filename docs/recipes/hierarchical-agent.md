---
status: Blueprint (design spec)
languages: [python, typescript]
agent_pattern: multi_agent
agent_role: "You are the lead of a hierarchical agent team. Break the goal into subtasks, delegate to workers, and synthesize their results into a final answer."
primitives: [tool_use, sub_agents]
runtime_modes:
  default:
    description: "Anthropic Claude — Opus for supervisor, Sonnet for specialists."
    swaps: {}
    context_budget: {input_max: 80000, output_max: 8000}
  local_only:
    description: "Self-hosted vLLM serving Llama 3 70B for all roles."
    swaps:
      stack/llm-claude: stack/llm-local-vllm
    context_budget: {input_max: 32000, output_max: 4000}
smoke_test:
  ready: "curl -sf http://localhost:8000/health"
  exercise: |
    curl -sf -X POST http://localhost:8000/task \
      -H 'content-type: application/json' \
      -d '{"task":"write a one-paragraph explainer about Postgres MVCC"}'
  assert_jq: '.deliverable | length > 0'
cost_profile:
  tier: medium
  sources: [anthropic]
  typical_run_usd: 0.06
model_recommendation:
  supervisor: claude-opus-4-7
  researcher: claude-sonnet-4-6
  writer: claude-sonnet-4-6
  reviewer: claude-sonnet-4-6
env_overrides:
  APP_PORT: 8000
est_tokens: 5000
required_files:
  - Dockerfile
  - docker-compose.yml
  - .github/workflows/ci.yml
  - app/main.py
  - app/graph/supervisor.py
  - app/agents/researcher.py
  - app/agents/writer.py
  - app/agents/reviewer.py
  - tests/unit/test_agents.py
  - tests/integration/test_supervisor.py
  - tests/eval/test_handoff.py
recipe_dependencies:
  python:
    fastapi: ">=0.110.0"
    langgraph: ">=0.2.0"
    langgraph-supervisor: ">=0.0.6"
    pydantic-settings: ">=2.0.0"
    sqlalchemy: ">=2.0.0"
    asyncpg: ">=0.29.0"
    redis: ">=5.0.0"
    structlog: ">=24.1.0"
    langfuse: ">=2.0.0"
  typescript:
    hono: "^4.0.0"
    "@ai-sdk/anthropic": "^1.0.0"
    ai: "^4.0.0"
    zod: "^3.23.0"
    ioredis: "^5.4.0"
    langfuse: "^3.0.0"
external_services:
  - postgres
  - redis
  - langfuse
capabilities:
  - relational.postgres
  - cache.redis
  - obs.langfuse
  - eval.promptfoo
acceptance_contracts:
  http_endpoints:
    - {path: /health, method: GET, status: 200}
    - {path: /task, method: POST, status: 200}
  required_env:
    - {name: ANTHROPIC_API_KEY, source: prompted}
    - {name: DATABASE_URL, source: 'capability:relational.postgres'}
  required_compose_services: [postgres, redis, langfuse]
  smoke_assertions:
    - {jq: '.deliverable | length > 0', against: smoke_test.exercise.stdout}
topology: multi-agent-hierarchical
roles:
  - name: supervisor
    description: "Coordinate the team by routing tasks to specialists and synthesizing their outputs."
    role_kind: supervisor
    model_hint: sonnet
    tools: []
  - name: researcher
    description: "Find information, extract facts, gather source material."
    role_kind: worker
    model_hint: sonnet
    tools: [search_web, extract_facts]
  - name: writer
    description: "Draft and revise content based on the research and any feedback."
    role_kind: worker
    model_hint: sonnet
    tools: [draft_content, revise_content]
  - name: reviewer
    description: "Evaluate content for accuracy, completeness, clarity, and style."
    role_kind: worker
    model_hint: sonnet
    tools: [evaluate_quality]
load_list:
  - {path: ../../vendored/blueprints/patterns/multi_agent/overview.md, required: true}
  - {path: ../frameworks/langgraph.md, required: true, when: "language == 'python'"}
  - {path: ../frameworks/vercel-ai-sdk.md, required: true, when: "language == 'typescript'"}
  - {path: ../cross-cutting/project-layout.md, required: true}
  - {path: ../stack/llm-claude.md, required: true}
  - {path: ../stack/api-fastapi.md, required: false, when: "language == 'python'"}
  - {path: ../stack/api-hono.md, required: false, when: "language == 'typescript'"}
  - {path: ../stack/relational-postgres.md, required: false, when: "capabilities contains 'relational.postgres'"}
  - {path: ../stack/cache-redis.md, required: false, when: "capabilities contains 'cache.redis'"}
  - {path: ../stack/tracing-langfuse.md, required: false, when: "capabilities contains 'obs.langfuse'"}
  - {path: ../cross-cutting/auth-jwt.md, required: false}
  - {path: ../cross-cutting/logging-structured.md, required: false}
  - {path: ../cross-cutting/observability.md, required: false}
  - {path: ../cross-cutting/rate-limiting.md, required: false}
  - {path: ../cross-cutting/prompt-management.md, required: false}
---

# Recipe: Hierarchical Agent

**Status:** Blueprint (design spec)

## Composes

- Pattern: [Multi-Agent Hierarchical](../../vendored/blueprints/patterns/multi_agent/overview.md)
- Framework (Py): [LangGraph](../frameworks/langgraph.md) (`langgraph-supervisor` for supervisor + sub-agent graphs)
- Framework (TS): [Vercel AI SDK](../frameworks/vercel-ai-sdk.md) (manual supervisor orchestration)
- Stack: [FastAPI](../stack/api-fastapi.md) / [Hono](../stack/api-hono.md), [Postgres](../stack/relational-postgres.md), [Redis](../stack/cache-redis.md), [Langfuse](../stack/tracing-langfuse.md)
- Cross-cutting: [Auth](../cross-cutting/auth-jwt.md), [Logging](../cross-cutting/logging-structured.md), [Observability](../cross-cutting/observability.md), [Rate limiting](../cross-cutting/rate-limiting.md)

### Load list

Feed these files to your AI coding assistant to build this agent:

**Core (always load):**
- `docs/recipes/hierarchical-agent.md` — this blueprint
- `vendored/blueprints/patterns/multi_agent/overview.md` — the hierarchical multi-agent pattern
- `docs/frameworks/langgraph.md` (Python) or `docs/frameworks/vercel-ai-sdk.md` (TypeScript)
- `docs/stack/llm-claude.md` — LLM integration and model selection

**Stack (load for Tier 2 — API-ready):**
- `docs/stack/api-fastapi.md` or `docs/stack/api-hono.md` — API layer
- `docs/stack/relational-postgres.md` — task result persistence
- `docs/stack/cache-redis.md` — rate limiting backend

**Production concerns (load for Tier 3):**
- `docs/cross-cutting/auth-jwt.md` · `docs/cross-cutting/rate-limiting.md` · `docs/cross-cutting/logging-structured.md` · `docs/cross-cutting/observability.md` · `docs/cross-cutting/testing-strategy.md`

**Scaffolding:** `docs/reference/docker-templates.md` · `docs/reference/docker-compose-template.md`

### Generation prompt

Copy-paste this into Claude Code or Cursor to scaffold this recipe before `agent-scaffold` ships:

````
You are scaffolding a runnable agent project from a spec at https://github.com/jagguvarma15/agent-deployments.

Step 1 — Fetch:
  - https://raw.githubusercontent.com/jagguvarma15/agent-deployments/main/catalog.yaml
  - https://raw.githubusercontent.com/jagguvarma15/agent-deployments/main/docs/recipes/hierarchical-agent.md
  - Every `load_list[].path` with `required: true` and `cache_tier: hot`.

Step 2 — Generate the project at `./hierarchical-agent/` matching the recipe's `required_files[]`:
  - model(s): supervisor=claude-opus-4-7, researcher=claude-sonnet-4-6, writer=claude-sonnet-4-6, reviewer=claude-sonnet-4-6
  - framework: langgraph (Python) or mastra (TS)
  - runtime_mode: default
  - env vars: from `catalog.recipes[hierarchical-agent].env_contract`

Step 3 — Bring it up: `docker compose up` + bootstrap per `LAYER_ORDER`.

Step 4 — Run the smoke test:

     curl -sf -X POST http://localhost:8000/task \
       -H 'content-type: application/json' \
       -d '{"task":"write a one-paragraph explainer about Postgres MVCC"}'

Step 5 — Validate against `catalog.recipes[hierarchical-agent].acceptance_contracts`.
````

## What it does

A hierarchical multi-agent system where a supervisor agent coordinates specialized worker agents to complete complex tasks. The supervisor receives a task, decides which worker(s) to delegate to, reviews their outputs, and iterates until the task is complete. Workers are compiled LangGraph sub-graphs, each with their own tools and state.

This implements **single-level hierarchy** — one supervisor with N workers. The supervisor treats each worker as a tool it can invoke.

## Architecture

```
Input (complex task)
    |
    v
┌──────────────────────────────────────────┐
│         Supervisor (LangGraph)           │
│                                          │
│   "I need the researcher to find..."     │
│       │                                  │
│       v                                  │
│   [Researcher sub-graph]                 │
│       │ ──> research results             │
│       v                                  │
│   "Now the writer should draft..."       │
│       │                                  │
│       v                                  │
│   [Writer sub-graph]                     │
│       │ ──> draft                        │
│       v                                  │
│   "The reviewer should check..."         │
│       │                                  │
│       v                                  │
│   [Reviewer sub-graph]                   │
│       │ ──> feedback                     │
│       v                                  │
│   "Writer, please revise based on..."    │
│       │                                  │
│       v                                  │
│   [Writer sub-graph]                     │
│       │ ──> revised draft                │
│       v                                  │
│   "Task complete"                        │
└──────────────────────────────────────────┘
    |
    v
Final output
```

## Data Models

### Python (Pydantic)

```python
from enum import Enum
from pydantic import BaseModel, Field


class WorkerName(str, Enum):
    researcher = "researcher"
    writer = "writer"
    reviewer = "reviewer"


class TaskRequest(BaseModel):
    task: str = Field(..., min_length=1, description="Complex task to complete")
    max_delegations: int = Field(default=10, ge=1, le=20, description="Max worker invocations")


class Delegation(BaseModel):
    """A single delegation from supervisor to worker."""
    worker: WorkerName
    task_description: str = Field(..., description="What the supervisor asked the worker to do")
    result: str = Field(..., description="Worker's output")
    iteration: int


class WorkerOutput(BaseModel):
    """Structured output from a worker sub-graph."""
    content: str = Field(..., description="The worker's response content")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Worker's self-assessed confidence")
    needs_revision: bool = Field(default=False)
    revision_notes: str | None = None


class SupervisorDecision(BaseModel):
    """What the supervisor decides to do next."""
    action: str = Field(..., description="delegate, revise, or complete")
    target_worker: WorkerName | None = None
    task_for_worker: str | None = None
    reasoning: str


class TaskResponse(BaseModel):
    output: str = Field(..., description="Final assembled output")
    delegations: list[Delegation]
    total_delegations: int
    trace_id: str
```

### TypeScript (Zod)

```typescript
import { z } from "zod";

export const WorkerName = z.enum(["researcher", "writer", "reviewer"]);
export type WorkerName = z.infer<typeof WorkerName>;

export const TaskRequest = z.object({
  task: z.string().min(1),
  max_delegations: z.number().min(1).max(20).default(10),
});
export type TaskRequest = z.infer<typeof TaskRequest>;

export const Delegation = z.object({
  worker: WorkerName,
  task_description: z.string(),
  result: z.string(),
  iteration: z.number(),
});
export type Delegation = z.infer<typeof Delegation>;

export const WorkerOutput = z.object({
  content: z.string(),
  confidence: z.number().min(0).max(1).default(0.8),
  needs_revision: z.boolean().default(false),
  revision_notes: z.string().optional(),
});
export type WorkerOutput = z.infer<typeof WorkerOutput>;

export const SupervisorDecision = z.object({
  action: z.string(),
  target_worker: WorkerName.optional(),
  task_for_worker: z.string().optional(),
  reasoning: z.string(),
});

export const TaskResponse = z.object({
  output: z.string(),
  delegations: z.array(Delegation),
  total_delegations: z.number(),
  trace_id: z.string(),
});
export type TaskResponse = z.infer<typeof TaskResponse>;
```

### LangGraph State (TypedDict)

```python
from typing import TypedDict
from langchain_core.messages import BaseMessage

class SupervisorState(TypedDict):
    messages: list[BaseMessage]
    task: str
    delegations: list[dict]
    delegation_count: int
    max_delegations: int
    status: str  # "delegating", "complete"
```

## API Contract

### `POST /task`

Submit a complex task for the hierarchical agent to complete.

**Request:**

```json
{
  "task": "Research AI agent design patterns and write a technical blog post with code examples",
  "max_delegations": 10
}
```

**Response (200):**

```json
{
  "output": "# AI Agent Design Patterns\n\n## Introduction\n\nAI agents are transforming...",
  "delegations": [
    {
      "worker": "researcher",
      "task_description": "Research current AI agent design patterns, focusing on practical production implementations",
      "result": "Found 9 common patterns: RAG, ReAct, Routing...",
      "iteration": 1
    },
    {
      "worker": "writer",
      "task_description": "Draft a technical blog post based on the research findings",
      "result": "# AI Agent Design Patterns\n\n...",
      "iteration": 2
    },
    {
      "worker": "reviewer",
      "task_description": "Review the draft for technical accuracy and completeness",
      "result": "The draft covers 7 of 9 patterns. Missing: Memory and Hierarchical...",
      "iteration": 3
    },
    {
      "worker": "writer",
      "task_description": "Revise the draft to include Memory and Hierarchical patterns",
      "result": "# AI Agent Design Patterns (revised)\n\n...",
      "iteration": 4
    }
  ],
  "total_delegations": 4,
  "trace_id": "f6a7b8c9-d0e1-2345-f012-678901234567"
}
```

**Errors:**

| Status | Body | When |
|--------|------|------|
| 400 | `{"error": "Invalid request", "details": [...]}` | Empty task |
| 422 | `{"error": "Max delegations exceeded", "delegations_used": N}` | Hit delegation limit without completing |
| 500 | `{"error": "Task execution failed", "partial_output": "..."}` | Worker or supervisor error |

### `GET /health`

Returns `{"status": "ok"}`.

## Tool Specifications

### Researcher Worker Tools

#### `search_web`

| Field | Value |
|-------|-------|
| **Description** | Search the web for information on a topic. Returns relevant snippets and URLs. |
| **Parameter** | `query` (string, required) — Search query. |
| **Return type** | `string` — Formatted search results with titles, snippets, and URLs. |

#### `extract_facts`

| Field | Value |
|-------|-------|
| **Description** | Extract key facts and claims from a text passage. |
| **Parameter** | `text` (string, required) — Text to analyze. |
| **Return type** | `string` — Bulleted list of extracted facts. |

### Writer Worker Tools

#### `draft_content`

| Field | Value |
|-------|-------|
| **Description** | Generate a structured content draft from an outline or brief. |
| **Parameters** | `brief` (string, required) — Writing brief or outline. `format` (string, optional) — "markdown", "html". Default "markdown". |
| **Return type** | `string` — Formatted draft content. |

#### `revise_content`

| Field | Value |
|-------|-------|
| **Description** | Revise existing content based on feedback. |
| **Parameters** | `content` (string, required) — Original content. `feedback` (string, required) — Revision instructions. |
| **Return type** | `string` — Revised content. |

### Reviewer Worker Tools

#### `evaluate_quality`

| Field | Value |
|-------|-------|
| **Description** | Evaluate content for accuracy, completeness, clarity, and style. |
| **Parameter** | `content` (string, required) — Content to review. |
| **Return type** | `string` — Structured evaluation with scores and specific feedback per dimension. |

## Prompt Specifications

### Supervisor prompt

```
You are a project manager coordinating a team of specialists to complete a task.

Your team:
- researcher: Finds information, extracts facts, gathers source material
- writer: Creates content drafts and revisions
- reviewer: Evaluates quality, accuracy, and completeness

Your job:
1. Break the task into steps
2. Delegate each step to the right worker
3. Review worker outputs
4. Decide: delegate more work, request a revision, or mark complete

Rules:
- Always start with research before writing
- Always have the reviewer check the writer's work
- If the reviewer finds issues, send the writer a revision with specific feedback
- You have a maximum of {max_delegations} delegations — use them wisely
- When the task is complete to a satisfactory level, output the final result

Current task: {task}
```

**Design rationale:**
- **"Always start with research before writing"** — Prevents the supervisor from jumping to writing without evidence. Without this, the supervisor often delegates directly to the writer, producing content based only on the LLM's parametric memory.
- **"Send the writer a revision with specific feedback"** — Generic "make it better" re-delegation is wasteful. The prompt forces the supervisor to relay the reviewer's specific feedback.
- **Delegation budget** — Without a cap, the supervisor can loop indefinitely. The budget forces it to prioritize and converge.

### Worker prompts (via `create_react_agent`)

Workers don't have explicit system prompts — their behavior is defined by the tools they're given and the task description from the supervisor. The supervisor's delegation message acts as the worker's prompt:

```python
researcher = create_react_agent(
    llm,
    tools=[search_web, extract_facts],
    name="researcher",
    prompt="You are a research specialist. Use your tools to find and verify information."
)

writer = create_react_agent(
    llm,
    tools=[draft_content, revise_content],
    name="writer",
    prompt="You are a skilled content writer. Use your tools to create and revise content."
)

reviewer = create_react_agent(
    llm,
    tools=[evaluate_quality],
    name="reviewer",
    prompt="You are a quality reviewer. Evaluate content rigorously and provide specific, actionable feedback."
)
```

### TypeScript equivalent

In the TypeScript track, the supervisor is a loop calling `generateObject({ schema: SupervisorDecision })`, and workers are individual `generateText()` calls:

```typescript
while (state.status !== "complete" && state.delegation_count < maxDelegations) {
  const decision = await generateObject({
    model: anthropic(config.supervisorModel),
    schema: SupervisorDecision,
    system: SUPERVISOR_PROMPT,
    prompt: buildSupervisorContext(state),
  });

  if (decision.object.action === "complete") break;

  const workerResult = await runWorker(
    decision.object.target_worker,
    decision.object.task_for_worker,
  );
  state.delegations.push({ ...decision.object, result: workerResult });
  state.delegation_count++;
}
```

## Key files

> Follows the canonical [project layout](../cross-cutting/project-layout.md) — `app/` package for Python, `src/` for TypeScript, `tests/{unit,integration,eval}/` for both.

### Python track

| File | Role |
|------|------|
| `app/main.py` | FastAPI entrypoint with lifespan, routers, health check |
| `app/settings.py` | Config: model names, max delegations |
| `app/models/schemas.py` | All Pydantic models and LangGraph state TypedDict |
| `app/agent/supervisor.py` | Supervisor agent using `langgraph-supervisor` |
| `app/agent/workers/researcher.py` | Researcher sub-graph: `create_react_agent` with search/extract tools |
| `app/agent/workers/writer.py` | Writer sub-graph: `create_react_agent` with draft/revise tools |
| `app/agent/workers/reviewer.py` | Reviewer sub-graph: `create_react_agent` with evaluate tool |
| `app/tools/web_search.py` | Web search tool (mock for local dev) |
| `app/tools/content.py` | Content drafting and revision tools |
| `app/tools/evaluate.py` | Quality evaluation tool |
| `app/api/task.py` | `/task` endpoint — accepts complex task, returns final output |

### TypeScript track

| File | Role |
|------|------|
| `src/index.ts` | Hono entrypoint with routes and health check |
| `src/config.ts` | Zod-validated env config |
| `src/schemas/index.ts` | All Zod schemas |
| `src/agent/supervisor.ts` | Supervisor loop: decide → delegate → review → decide |
| `src/agent/workers/researcher.ts` | Researcher: `generateText()` with search tools |
| `src/agent/workers/writer.ts` | Writer: `generateText()` with content tools |
| `src/agent/workers/reviewer.ts` | Reviewer: `generateText()` with evaluate tool |
| `src/tools/web-search.ts` | Web search tool |
| `src/tools/content.ts` | Content tools |
| `src/tools/evaluate.ts` | Quality evaluation tool |
| `src/api/task.ts` | `/task` route handler |

### Key implementation pattern (Python)

```python
from langgraph_supervisor import create_supervisor
from langgraph.prebuilt import create_react_agent

researcher = create_react_agent(llm, tools=[search_web, extract_facts], name="researcher")
writer = create_react_agent(llm, tools=[draft_content, revise_content], name="writer")
reviewer = create_react_agent(llm, tools=[evaluate_quality], name="reviewer")

supervisor = create_supervisor(
    agents=[researcher, writer, reviewer],
    model=llm,
    prompt="You are a project manager. Delegate tasks to your team...",
)

app = supervisor.compile()
result = app.invoke({"messages": [("user", task)]})
```

## Implementation Roadmap

| Step | Task | Key deliverables |
|------|------|-----------------|
| 1 | **Project scaffolding** | FastAPI/Hono app with `/health`, settings, structured logging |
| 2 | **Data models** | All Pydantic + Zod schemas, LangGraph state TypedDict |
| 3 | **Worker tools** | Mock tools for search, content drafting, quality evaluation |
| 4 | **Researcher worker** | `create_react_agent` with search/extract tools |
| 5 | **Writer worker** | `create_react_agent` with draft/revise tools |
| 6 | **Reviewer worker** | `create_react_agent` with evaluate tool |
| 7 | **Supervisor agent** | `create_supervisor` with worker descriptions and delegation prompt |
| 8 | **Delegation tracking** | Record each delegation with worker, task, result, iteration |
| 9 | **Termination logic** | Stop on "complete" decision or max_delegations reached |
| 10 | **API endpoint** | `POST /task` wired to supervisor, trace ID generation |
| 11 | **Cross-cutting** | JWT auth, rate limiting, Langfuse tracing per delegation |
| 12 | **Unit tests** | Worker isolation, supervisor decision parsing, delegation limits |
| 13 | **Integration + eval** | End-to-end task with real LLM, verify research→write→review flow |

## Environment & Deployment

### Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `SUPERVISOR_MODEL` | No | `claude-sonnet-4-6-20250514` | Model for supervisor decisions |
| `WORKER_MODEL` | No | `claude-sonnet-4-6-20250514` | Model for worker agents |
| `MAX_DELEGATIONS` | No | `10` | Default max worker invocations |
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
| Postgres | Yes | Task results and delegation history |
| Redis | Yes | Rate limiting backend |
| Qdrant | No | Not needed — workers use tools, not document retrieval |
| Langfuse | Recommended | Supervisor + worker delegation tracing (skip for local dev) |

## Test Strategy

### Unit tests

```python
def test_delegation_limit_enforced():
    """Supervisor stops after max_delegations even if not complete."""
    # Run with max_delegations=3
    # Assert exactly 3 delegations, status indicates limit reached

def test_supervisor_delegates_research_first(mock_llm_client):
    """First delegation should always go to the researcher."""
    result = run_supervisor("Write a blog post about X", max_delegations=5)
    assert result["delegations"][0]["worker"] == "researcher"

def test_reviewer_feedback_passed_to_writer(mock_llm_client):
    """When reviewer finds issues, writer gets specific feedback in next delegation."""
    # Mock reviewer to return "missing section X"
    # Assert writer's next task_description includes "missing section X"
```

### Integration tests (main branch only)

```python
async def test_full_task_e2e():
    """End-to-end: supervisor coordinates research → write → review → revise."""
    response = await client.post("/task", json={
        "task": "Write a short technical summary of the RAG pattern",
        "max_delegations": 8,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["total_delegations"] >= 3  # at least research + write + review
    assert len(data["output"]) > 200
    workers_used = {d["worker"] for d in data["delegations"]}
    assert "researcher" in workers_used
    assert "writer" in workers_used
```

### Eval assertions

- Supervisor always delegates to researcher before writer
- Reviewer feedback triggers at least one writer revision
- Final output incorporates facts from the research step
- Delegation count stays within budget
- No worker is called more than 4 times (prevents loops)

## Eval Dataset

```jsonl
{"input": {"task": "Write a technical blog post about the RAG pattern"}, "expected_min_delegations": 3, "expected_workers": ["researcher", "writer", "reviewer"]}
{"input": {"task": "Create a comparison of Python vs Go for building microservices"}, "expected_min_delegations": 3, "expected_workers": ["researcher", "writer", "reviewer"]}
{"input": {"task": "Research and summarize the latest trends in LLM agent frameworks"}, "expected_min_delegations": 2, "expected_workers": ["researcher", "writer"]}
{"input": {"task": "Write a tutorial on using Docker Compose for local development"}, "expected_min_delegations": 3, "expected_workers": ["researcher", "writer", "reviewer"]}
{"input": {"task": "Draft release notes for a new version of our API"}, "expected_min_delegations": 2, "expected_workers": ["writer", "reviewer"]}
```

See [eval-data guide](../cross-cutting/eval-data.md) for generation + curation patterns.

## Design Decisions

- **`langgraph-supervisor` for orchestration:** Purpose-built for the supervisor pattern. Each worker is a compiled sub-graph that the supervisor invokes as a tool. Clean separation of concerns.
- **Workers as sub-graphs:** Each worker is an independent `create_react_agent` with its own tools. Workers don't know about each other — the supervisor manages all coordination.
- **Iterative refinement:** The supervisor can call the same worker multiple times (e.g., writer → reviewer → writer). This enables revision loops without hardcoding the sequence.
- **LangGraph state for coordination:** The supervisor's state tracks all delegations and results. Checkpointing enables resuming long multi-agent tasks.
- **Termination by supervisor judgment:** The supervisor decides when the task is complete based on worker outputs. No fixed number of delegation rounds.
- **Delegation budget as safety net:** The `max_delegations` cap prevents runaway loops where the supervisor endlessly requests revisions. It forces convergence.
