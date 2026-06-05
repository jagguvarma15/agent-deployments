---
id: pydantic_ai
language: python
package: pydantic-ai
versions:
  minimum: ">=0.1.0"
---

# Framework: Pydantic AI

**Language:** Python
**Install:** `uv add pydantic-ai[anthropic]`
**Version pinned:** >=0.1.0

## Core abstractions

- **Agent:** The central class. Wraps a model, system prompt, tools, and result type. Calling `agent.run()` executes a full reason-act-observe loop until the agent produces a result.
- **Tool:** A decorated Python function (`@agent.tool` or `@agent.tool_plain`) that the agent can call. Tools receive typed arguments and return typed results.
- **Result type:** A Pydantic model that defines the structured output the agent must produce. The framework validates the LLM's output against this schema automatically.
- **Dependencies:** Typed context injected into tools via `@agent.tool` (as opposed to `@agent.tool_plain`). Useful for passing DB connections, API clients, or user context.
- **System prompt:** Static string or dynamic function that sets the agent's behavior. Dynamic prompts can use dependencies.

## Patterns it supports well

- **Routing + Tool Use** — Structured `result_type` makes intent classification natural. Separate agents per specialist with isolated tool sets. This is the pattern used in `customer-support-triage`.
- **ReAct** — `agent.run()` is a built-in ReAct loop. The agent reasons, calls tools, observes results, and loops until it produces the result type. Used in `research-assistant`.
- **RAG** — Retrieval as a tool, generation via the agent. Type-safe citation schemas via `result_type`. Used in `docs-rag-qa`.
- **Prompt Chaining** — Sequential `agent.run()` calls with different `result_type` per stage. Type safety between stages.
- **Parallel Calls** — `asyncio.gather()` with multiple `agent.run()` calls. Async-first design makes this natural.

## Patterns where it's awkward

- **Plan-and-Execute** — No built-in state management or checkpointing. You'd manage the plan/reflect state yourself.
- **Multi-Agent (hierarchical)** — No supervisor abstraction. You'd orchestrate agent-calling-agent manually.
- **Memory** — No built-in persistence. You'd integrate with an external memory store via tools.

## Idiomatic minimal example

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

## Strengths

- **Type safety** — Pydantic models for inputs, outputs, and tool signatures. Validation is automatic.
- **Minimal boilerplate** — An agent with tools is ~10 lines. No graph to define, no nodes to wire.
- **Async-first** — Built on asyncio. Parallel tool calls and concurrent agents work naturally.
- **Framework-agnostic models** — Supports Anthropic, OpenAI, Gemini, Ollama, and more via a clean provider interface.
- **Testable** — `TestModel` and `FunctionModel` allow deterministic testing without hitting an LLM.

## Trade-offs

- **No state management** — Unlike LangGraph, there's no checkpointer or state graph. Complex multi-step workflows require manual state handling.
- **No built-in multi-agent** — Each agent is independent. Orchestrating multiple agents is your responsibility.
- **Simpler = less control** — The ReAct loop is opaque. You can't easily inject logic between reason and act steps (LangGraph lets you add nodes anywhere).
- **Younger ecosystem** — Smaller community and fewer integrations compared to LangChain/LangGraph.

## Used in this repo

| Prototype | Role |
|-----------|------|
| `customer-support-triage` | Classifier agent with `result_type=ClassificationResult`, specialist agents per intent |
| `docs-rag-qa` | RAG agent with Qdrant retrieval as a tool |
| `research-assistant` | ReAct agent with web search tool |
| `content-pipeline` | Planned for prompt chaining (skeleton) |
| `parallel-enricher` | Planned for parallel `asyncio.gather()` pattern (skeleton) |

## Reference implementations

- [recipes/customer-support-triage.md](../recipes/customer-support-triage.md) — Routing + Tool Use
- [recipes/docs-rag-qa.md](../recipes/docs-rag-qa.md) — Agentic RAG
- [recipes/research-assistant.md](../recipes/research-assistant.md) — ReAct research agent

## Version notes

One-line summary: the `>=0.1.0` floor is what stabilizes the agent + `output_type` (renamed from `result_type`) surface the recipes rely on; treat the 0.0.x line as legacy.

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
