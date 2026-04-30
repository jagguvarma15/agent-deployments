# Recipe: Hierarchical Agent

**Status:** Skeleton (design intent)

**Composes:**

- Pattern: [Multi-Agent Hierarchical](../patterns/multi-agent-hierarchical.md)
- Framework (Py): [LangGraph](../frameworks/langgraph.md) (`langgraph-supervisor` for supervisor + sub-agent graphs)
- Framework (TS): [Vercel AI SDK](../frameworks/vercel-ai-sdk.md) (manual supervisor orchestration)
- Stack: [FastAPI](../stack/api-fastapi.md) / [Hono](../stack/api-hono.md), [Postgres](../stack/relational-postgres.md), [Redis](../stack/cache-redis.md), [Langfuse](../stack/tracing-langfuse.md)
- Cross-cutting: [Auth](../cross-cutting/auth-jwt.md), [Logging](../cross-cutting/logging-structured.md), [Observability](../cross-cutting/observability.md), [Rate limiting](../cross-cutting/rate-limiting.md)

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

## Intended key files

### Python track

| File | Role |
|------|------|
| `app/agent/supervisor.py` | Supervisor agent using `langgraph-supervisor`. Defines worker descriptions and delegation logic. |
| `app/agent/workers/researcher.py` | Researcher sub-graph: web search, fact extraction |
| `app/agent/workers/writer.py` | Writer sub-graph: content drafting, revision |
| `app/agent/workers/reviewer.py` | Reviewer sub-graph: quality evaluation, feedback |
| `app/models/schemas.py` | `TaskState`, `DelegationResult`, `WorkerOutput` schemas |
| `app/api/task.py` | `/task` endpoint — accepts complex task, returns final output |

### Key implementation pattern (Python)

```python
from langgraph_supervisor import create_supervisor
from langgraph.prebuilt import create_react_agent

researcher = create_react_agent(llm, tools=[search, extract_facts], name="researcher")
writer = create_react_agent(llm, tools=[draft, revise], name="writer")
reviewer = create_react_agent(llm, tools=[evaluate], name="reviewer")

supervisor = create_supervisor(
    agents=[researcher, writer, reviewer],
    model=llm,
    prompt="You are a project manager. Delegate tasks to your team...",
)

app = supervisor.compile()
result = app.invoke({"messages": [("user", "Write a report on AI agent patterns")]})
```

## Example interaction

```bash
curl -X POST http://localhost:8000/task \
  -H "Content-Type: application/json" \
  -d '{"task": "Research AI agent design patterns and write a technical blog post with code examples"}'
```

Expected response:

```json
{
  "output": "# AI Agent Design Patterns\n\n...",
  "delegations": [
    {"worker": "researcher", "task": "Research AI agent design patterns", "result": "..."},
    {"worker": "writer", "task": "Draft blog post from research", "result": "..."},
    {"worker": "reviewer", "task": "Review draft for accuracy", "result": "..."},
    {"worker": "writer", "task": "Revise based on feedback", "result": "..."}
  ],
  "total_delegations": 4,
  "trace_id": "..."
}
```

## Design intent

- **`langgraph-supervisor` for orchestration:** Purpose-built for the supervisor pattern. Each worker is a compiled sub-graph that the supervisor invokes as a tool. Clean separation of concerns.
- **Workers as sub-graphs:** Each worker is an independent `create_react_agent` with its own tools. Workers don't know about each other — the supervisor manages all coordination.
- **Iterative refinement:** The supervisor can call the same worker multiple times (e.g., writer → reviewer → writer). This enables revision loops without hardcoding the sequence.
- **LangGraph state for coordination:** The supervisor's state tracks all delegations and results. Checkpointing enables resuming long multi-agent tasks.
- **Termination by supervisor judgment:** The supervisor decides when the task is complete based on worker outputs. No fixed number of delegation rounds.
