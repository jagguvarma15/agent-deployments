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
