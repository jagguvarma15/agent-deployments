---
id: pydantic_ai
language: python
package: pydantic-ai
versions:
  minimum: ">=0.1.0"
  last_known_good: "0.1.0"
  notes: "The >=0.1.0 floor is what stabilizes the agent + `output_type` (renamed from `result_type`) surface the recipes rely on; treat the 0.0.x line as legacy."
tags: [python, type-safe, mcp-native, agentic-loop]
when_to_load: "recipe.framework == 'pydantic_ai'"
---

# Framework: Pydantic AI

**Language:** Python
**Install:** `uv add pydantic-ai[anthropic]`
**Version pinned:** >=0.1.0

## When to choose Pydantic AI

Pydantic AI is the right fit when an agent is a single typed loop — classify-and-route, retrieve-and-answer, single-purpose ReAct — and the minimal-boilerplate path is the goal. Type safety is the central value: Pydantic models for inputs, outputs, and tool signatures with automatic validation. An agent with tools is roughly ten lines; no graph to define, no nodes to wire. Async-first design means parallel tool calls and concurrent agents compose with `asyncio.gather()` naturally. The provider interface is framework-agnostic — Anthropic, OpenAI, Gemini, Ollama all bind through a clean abstraction. Testability is first-class: `TestModel` and `FunctionModel` allow deterministic testing without hitting an LLM.

Core abstractions:

- **Agent:** The central class. Wraps a model, system prompt, tools, and result type. Calling `agent.run()` executes a full reason-act-observe loop until the agent produces a result.
- **Tool:** A decorated Python function (`@agent.tool` or `@agent.tool_plain`) that the agent can call. Tools receive typed arguments and return typed results.
- **Result type:** A Pydantic model that defines the structured output the agent must produce. The framework validates the LLM's output against this schema automatically.
- **Dependencies:** Typed context injected into tools via `@agent.tool` (as opposed to `@agent.tool_plain`). Useful for passing DB connections, API clients, or user context.
- **System prompt:** Static string or dynamic function that sets the agent's behavior. Dynamic prompts can use dependencies.

## Minimal agent

```python
from pydantic_ai import Agent

agent = Agent(
    "anthropic:claude-sonnet-4-6-20250514",
    system_prompt="You are a helpful assistant.",
)

@agent.tool_plain
async def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"

result = await agent.run("What is MCP?")
print(result.data)
```

## Tools

Tools are decorated Python callables. `@agent.tool_plain` registers a tool whose signature reaches the model directly — the parameter annotations and docstring become the schema. `@agent.tool` registers a tool that also receives a typed `RunContext[Deps]` first parameter, used to pass DB connections, HTTP clients, or per-request context without globals. Both flavors validate return types via Pydantic so a tool can't accidentally hand back a shape the model wasn't told about.

## Structured output

Pass `output_type=SchemaClass` (or the legacy `result_type=` alias) when constructing the `Agent` and the framework binds the model's response to a Pydantic schema. Validation runs on every turn; if the model emits a shape that doesn't fit, Pydantic AI raises a retryable error and re-prompts. The result of `agent.run()` carries the validated instance on `.data`.

## Memory

Pydantic AI does not ship a built-in memory primitive. Conversation history is the user's responsibility: pass the message list to `agent.run()` via `message_history`, persist it externally (Postgres, Redis, an in-process dict), and reload on the next turn. The history shape is typed — see Upgrade gotchas below for the OpenAI-shape mixing pitfall. For long-term memory (per-user facts, summarized history), the canonical pattern is a retrieval tool that the agent calls when relevant; the [`memory`](../patterns/memory.md) pattern doc walks through the conversation-buffer + retrieval shape Pydantic AI agents reach for.

## Streaming

`agent.run_stream()` returns an async stream of partial responses. For structured-output agents, the stream emits incremental Pydantic models as the response materializes — a streamed `output_type` is fully typed at every yield. Pair with FastAPI's `StreamingResponse` for HTTP transport.

## Observability

Pydantic AI exports OpenTelemetry traces natively when the OTel SDK is configured in-process: agent runs, tool calls, and LLM requests all become spans. There's no first-class LangSmith-equivalent dashboard; OTel + a backend (Jaeger, Tempo, Honeycomb) is the standard path. Per-tool span attributes carry the arguments and return shapes so traces correlate cleanly with the typed signatures.

## Anti-patterns

- **Plan & Execute** — No built-in state management or checkpointing. You'd manage the plan/reflect state yourself; LangGraph is the better fit when state and checkpointing are load-bearing.
- **Multi-Agent (hierarchical)** — No supervisor abstraction. You'd orchestrate agent-calling-agent manually; CrewAI for crews, LangGraph for supervisor-shaped graphs.
- **Persistent memory across sessions.** No built-in persistence. You'd integrate with an external memory store via tools.
- **Need to inject logic between reason and act.** The ReAct loop is opaque. You can't easily insert logic between reason and act steps the way LangGraph nodes let you. If that's the requirement, choose LangGraph.
- **Heavy ecosystem reliance.** Smaller community and fewer integrations compared to LangChain/LangGraph. Pre-built retrievers, message-history backends, or specialty tools may exist there but not here; expect to write the integration yourself.

## Composition matrix

- **Routing + Tool Use** — Structured `output_type` makes intent classification natural. Separate agents per specialist with isolated tool sets. The pattern used in `customer-support-triage`.
- **ReAct** — `agent.run()` is a built-in ReAct loop. The agent reasons, calls tools, observes results, and loops until it produces the result type. Used in `research-assistant`.
- **RAG** — Retrieval as a tool, generation via the agent. Type-safe citation schemas via `output_type`. Used in `docs-rag-qa`.
- **Prompt Chaining** — Sequential `agent.run()` calls with different `output_type` per stage. Type safety between stages.
- **Parallel Calls** — `asyncio.gather()` with multiple `agent.run()` calls. Async-first design makes this natural.

## MCP integration

Pydantic AI ships first-class MCP client support via `pydantic_ai.mcp.MCPServerStreamableHTTP` and `MCPServerStdio`. Tools discovered from connected MCP servers join the agent's tool surface alongside `@agent.tool` Python-decorated tools.

**Streamable HTTP transport (the `mcp.tavily` capability):**

```python
import os
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP

tavily = MCPServerStreamableHTTP(
    url="https://mcp.tavily.com/mcp/",
    headers={"Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}"},
)

agent = Agent(
    "anthropic:claude-sonnet-4-6",
    mcp_servers=[tavily],
    system_prompt="You are a research assistant.",
)

async with agent.run_mcp_servers():
    result = await agent.run("Compare GraphQL vs gRPC for streaming workloads.")
    print(result.output)
```

`agent.run_mcp_servers()` opens transports, discovers tools, registers them; the surrounding `async with` handles lifecycle.

**Stdio transport (locally-spawned servers):**

```python
from pydantic_ai.mcp import MCPServerStdio

postgres = MCPServerStdio(
    "npx",
    args=["-y", "@modelcontextprotocol/server-postgres", os.environ["DATABASE_URL"]],
)

agent = Agent("anthropic:claude-sonnet-4-6", mcp_servers=[tavily, postgres])
```

Tools are exposed under their MCP-declared names; reference them by that name in system prompts.

## Version notes

The `>=0.1.0` floor is what stabilizes the agent + `output_type` (renamed from `result_type`) surface the recipes rely on; treat the 0.0.x line as legacy.

| Version | Status | Notes |
|---------|--------|-------|
| `< 0.1.0` | Unsupported | Pre-`output_type` rename; the `result_type` keyword recipes used in early drafts is gone. `@agent.tool` decorator semantics also moved during the 0.0.x line. |
| `>=0.1.0` | Recommended | Current pin in the frontmatter. Validated against [`../recipes/customer-support-triage.md`](../recipes/customer-support-triage.md), [`../recipes/docs-rag-qa.md`](../recipes/docs-rag-qa.md), [`../recipes/research-assistant.md`](../recipes/research-assistant.md). |
| `0.2+` | Untested | Likely fine; the 0.1 → 0.2 cycle has been additive. Re-verify `result_type` / `output_type` aliases before bumping. |

### Upgrade gotchas

- **`result_type` → `output_type` rename.** Pydantic AI renamed the agent's structured-output keyword during the 0.0.x → 0.1.0 transition. Both spellings still parse on the 0.1.x line but `output_type` is canonical; older recipe drafts that used `result_type` should be migrated when the doc is touched.
- **`message_history` shape.** The history-passing parameter takes a typed list, not raw `{"role": ..., "content": ...}` dicts. Mixing in OpenAI-shaped messages results in a silent validation failure where the agent forgets prior turns.
- **Tool decorators.** `@agent.tool_plain` (no dependency injection) vs `@agent.tool` (typed deps via `RunContext`) are not interchangeable. Recipes that need a DB connection or HTTP client should use `@agent.tool` with `RunContext[Deps]`.

### Why these bounds

The `>=0.1.0` floor exists because that release cut over to the stable `Agent(...)` surface (typed deps via `RunContext`, the renamed `output_type` keyword, the structured-output validation path the recipes assume). Pre-0.1 the API was still moving fast enough that pinned recipes broke between minor bumps. No recorded upper bound: the post-0.1 line has stayed source-compatible so far, but verify the structured-output contract against `customer-support-triage` before adopting a new minor.

## Used in this repo

| Prototype | Role |
|-----------|------|
| `customer-support-triage` | Classifier agent with `output_type=ClassificationResult`, specialist agents per intent |
| `docs-rag-qa` | RAG agent with Qdrant retrieval as a tool |
| `research-assistant` | ReAct agent with web search tool |
| `content-pipeline` | Planned for prompt chaining (skeleton) |
| `parallel-enricher` | Planned for parallel `asyncio.gather()` pattern (skeleton) |

Reference implementations:

- [recipes/customer-support-triage.md](../recipes/customer-support-triage.md) — Routing + Tool Use
- [recipes/docs-rag-qa.md](../recipes/docs-rag-qa.md) — Agentic RAG
- [recipes/research-assistant.md](../recipes/research-assistant.md) — ReAct research agent
