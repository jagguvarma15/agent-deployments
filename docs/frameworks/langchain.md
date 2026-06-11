---
id: langchain
language: python
package: langchain
versions:
  minimum: "0.3.0"
  last_known_good: "0.3.18"
  notes: "0.3.x consolidated agents under langchain.agents; earlier versions split between langchain and langchain-experimental. >=0.4 may break the tool decorator surface — pin tight."
extra_packages:
  - {name: langchain-anthropic, minimum: "0.2.0"}
  - {name: langchain-core, minimum: "0.3.0"}
---

# Framework: LangChain

**Language:** Python
**Install:** `uv add langchain langchain-anthropic langchain-core`
**Version pinned:** `>=0.3.0` (last known good: `0.3.18`)

LangChain is the broad runnable + integration toolkit: chat models, tools, retrievers, message-history wrappers, document loaders. For most agent loops you reach for `AgentExecutor` + `create_tool_calling_agent` and let the model drive a tool-use loop. When you need explicit state, conditional edges, or checkpointing, [LangGraph](langgraph.md) is the right layer; LangChain is the layer underneath it.

## When to choose LangChain

| You need | Pick |
|----------|------|
| A tool-using agent with no explicit state machine | **LangChain** (`AgentExecutor`) |
| Stateful multi-step flow, checkpointing, multi-agent | [LangGraph](langgraph.md) |
| Single agent, typed tools, structured `result_type` | [Pydantic AI](pydantic-ai.md) |
| A crew of role-specialized agents | [CrewAI](crewai.md) |
| Direct control over the Anthropic API surface | [`anthropic` SDK](../stack/llm-claude.md) (no framework) |

Pick LangChain over LangGraph when the agent loop is straightforward (model decides which tools to call, executor runs them, model decides when it's done) and you want to lean on the ecosystem — `langchain-community` retrievers, document loaders, message-history adapters. Reach for LangGraph the moment you need conditional branching, parallel fan-out, or durable state across calls.

## Minimal agent

A complete tool-calling agent, ~50 lines:

```python
"""Minimal LangChain agent with Anthropic + two tools.

Run:
    ANTHROPIC_API_KEY=... uv run --with 'langchain>=0.3,<0.4' \
        --with 'langchain-anthropic>=0.2' python agent.py
"""
from __future__ import annotations

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool


@tool
def search(query: str) -> str:
    """Search the knowledge base. Returns top results as plain text."""
    return f"(mock) top result for: {query}"


@tool
def get_weather(city: str) -> str:
    """Return the current weather for `city`."""
    return f"(mock) 18C and clear in {city}"


def main() -> None:
    llm = ChatAnthropic(model="claude-sonnet-4-6-20250514", temperature=0)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a concise research assistant. Use tools when helpful."),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    agent = create_tool_calling_agent(llm, tools=[search, get_weather], prompt=prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=[search, get_weather],
        max_iterations=5,
        handle_parsing_errors=True,
        return_intermediate_steps=False,
    )
    result = executor.invoke({"input": "What's the weather in Berlin and find me a recipe doc?"})
    print(result["output"])


if __name__ == "__main__":
    main()
```

Notes:

- `create_tool_calling_agent` is the 0.3.x replacement for the older `initialize_agent` and `OpenAIFunctionsAgent`. Use it for any Claude / OpenAI tool-use loop.
- `max_iterations` is a hard stop. Without it a confused model can loop indefinitely calling the same tool.
- `handle_parsing_errors=True` swallows malformed tool calls and re-prompts. In production, set it to a callable that logs the malformed payload before retrying so you can catch prompt regressions.

## Tools

```python
from typing import Annotated
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class LookupArgs(BaseModel):
    """Structured args — the model receives the schema, not free text."""

    user_id: str = Field(description="Internal user id, e.g. 'usr_1234'")
    fields: list[str] = Field(default_factory=list, description="Subset of profile fields to return")


@tool("lookup_user", args_schema=LookupArgs)
def lookup_user(user_id: str, fields: list[str]) -> dict:
    """Fetch a user record. Use this when the user mentions an id or email."""
    return {"user_id": user_id, "name": "Ada Lovelace", "fields_returned": fields}


@tool
async def fetch_url(url: Annotated[str, "Absolute https URL"]) -> str:
    """Async tool — LangChain awaits these inside the executor."""
    import httpx

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.text[:2000]
```

Conventions worth pinning:

- Prefer `args_schema=...` with a Pydantic model over Annotated free-form types when the tool has more than one argument. The schema is what the model sees in its tool-list prompt; explicit `Field(description=...)` directly improves tool-selection accuracy.
- Async tools are first-class. The executor uses `ainvoke` automatically when any tool is async — don't mix sync `invoke` with async tools or you'll deadlock the event loop.
- Tools that hit a remote system must own their own timeout. The executor's `max_execution_time` is a wall clock across the *whole* run, not per-tool.

Error handling inside a tool:

```python
@tool
def divide(a: float, b: float) -> float:
    """Divide a by b."""
    if b == 0:
        # Raise a ToolException; AgentExecutor.handle_tool_error returns the
        # message to the model so it can recover instead of crashing.
        from langchain_core.tools import ToolException
        raise ToolException("Cannot divide by zero — ask the user to clarify.")
    return a / b


executor = AgentExecutor(
    agent=agent,
    tools=[divide],
    handle_tool_error=True,  # or a callable: lambda e: f"Tool failed: {e}"
)
```

## Structured output

Two distinct paths — pick by whether you need tool use.

**No tools (one-shot structured output):**

```python
from pydantic import BaseModel
from langchain_anthropic import ChatAnthropic


class Triage(BaseModel):
    intent: str
    confidence: float
    urgency: str


llm = ChatAnthropic(model="claude-sonnet-4-6-20250514", temperature=0)
structured = llm.with_structured_output(Triage)
result: Triage = structured.invoke("My order is late and I'm furious.")
assert isinstance(result, Triage)
```

`with_structured_output` internally registers a single tool with the model and forces it. Cheaper and faster than `AgentExecutor` for one-shot extraction.

**Agent path with a final structured answer:**

The pattern that survives the upgrade churn: end the agent with a `final_answer` tool whose schema is your result type, and key off it in the executor loop.

```python
from langchain_core.tools import tool
from pydantic import BaseModel


class Answer(BaseModel):
    summary: str
    citations: list[str]


@tool("final_answer", args_schema=Answer)
def final_answer(summary: str, citations: list[str]) -> dict:
    """Emit the final structured answer and stop. Always call this last."""
    return {"summary": summary, "citations": citations}


# Add `final_answer` to the tools list. The model is told (in the system
# prompt) it must invoke `final_answer` exactly once at the end.
```

The simple `with_structured_output` wrapper does not work mid-agent-loop in 0.3.x — keep the two paths separate.

## Memory

LangChain dropped the legacy `ConversationBufferMemory` from the agent surface in 0.3. The 0.3.x idiom is `RunnableWithMessageHistory` plus a history backend.

In-memory (tests only):

```python
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

store: dict[str, InMemoryChatMessageHistory] = {}


def get_history(session_id: str) -> InMemoryChatMessageHistory:
    return store.setdefault(session_id, InMemoryChatMessageHistory())


chain_with_history = RunnableWithMessageHistory(
    executor,  # any Runnable; AgentExecutor counts
    get_session_history=get_history,
    input_messages_key="input",
    history_messages_key="chat_history",
)

chain_with_history.invoke(
    {"input": "Remember my name is Ada."},
    config={"configurable": {"session_id": "user-42"}},
)
```

Redis-backed (production) — see [`../stack/cache-redis.md`](../stack/cache-redis.md) for the connection pattern:

```python
from langchain_community.chat_message_histories import RedisChatMessageHistory


def get_history(session_id: str) -> RedisChatMessageHistory:
    return RedisChatMessageHistory(
        session_id=session_id,
        url="redis://localhost:6379/0",
        ttl=86400,  # one-day session window
    )
```

Postgres-backed — see [`../stack/relational-postgres.md`](../stack/relational-postgres.md):

```python
from langchain_community.chat_message_histories import PostgresChatMessageHistory


def get_history(session_id: str) -> PostgresChatMessageHistory:
    return PostgresChatMessageHistory(
        connection_string="postgresql://app:secret@localhost/agentdb",
        session_id=session_id,
        table_name="chat_history",
    )
```

For long-running conversations, layer a summarizer on top — `ConversationSummaryBufferMemory` is gone in 0.3; the replacement is a `RunnableLambda` that periodically calls Haiku to compress older turns.

## Observability

Two callback handlers cover almost every case.

Langfuse (recommended for self-hosted traces — see [`../stack/tracing-langfuse.md`](../stack/tracing-langfuse.md)):

```python
from langfuse.callback import CallbackHandler


langfuse_handler = CallbackHandler(
    public_key="pk-...",
    secret_key="sk-...",
    host="https://cloud.langfuse.com",
)
result = executor.invoke({"input": "..."}, config={"callbacks": [langfuse_handler]})
```

OpenTelemetry — every LangChain call emits spans through the OTel SDK if you set up the tracer provider before the executor runs. See [`../stack/opentelemetry.md`](../stack/opentelemetry.md):

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

# All ChatAnthropic and tool spans now propagate to OTel automatically.
```

Both handlers stack — `callbacks=[langfuse_handler, otel_handler]` is fine. Per-event payloads are the same callbacks API as 0.2; only the import paths moved.

## Streaming

Use `astream_events` to get a typed stream of every node + tool event. It is the only streaming API in 0.3.x that survives the executor — token-level streaming via `.stream()` skips tool boundaries.

```python
async for event in executor.astream_events(
    {"input": "Find me a recipe and summarize it."},
    version="v2",
):
    kind = event["event"]
    if kind == "on_chat_model_stream":
        chunk = event["data"]["chunk"]
        print(chunk.content, end="", flush=True)
    elif kind == "on_tool_start":
        print(f"\n[tool] {event['name']}({event['data']['input']})")
    elif kind == "on_tool_end":
        print(f"[tool→] {event['data']['output']}")
```

`version="v2"` is required in 0.3.x — `v1` is deprecated and the event names differ.

## Retrieval

LangChain's retriever interface is `BaseRetriever` — any vector store with a `.as_retriever()` method drops in. See [`../patterns/rag.md`](../patterns/rag.md) for the pattern and [`../stack/vector-qdrant.md`](../stack/vector-qdrant.md) for the canonical Qdrant collection layout.

```python
from langchain_qdrant import QdrantVectorStore
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool


vs = QdrantVectorStore.from_existing_collection(
    embedding=...,  # your embedding model
    collection_name="docs",
    url="http://localhost:6333",
)
retriever = vs.as_retriever(search_kwargs={"k": 4})


@tool
def search_docs(query: str) -> str:
    """Search the docs knowledge base. Returns up to 4 chunks."""
    docs = retriever.invoke(query)
    return "\n\n---\n\n".join(f"[{d.metadata.get('source', '?')}]\n{d.page_content}" for d in docs)
```

The retriever-as-tool pattern composes with `AgentExecutor` without a separate `RetrievalQA` chain. `RetrievalQA` is still available but is one of the least-stable surfaces across minor versions — prefer the tool form.

## Testing

`FakeListChatModel` (or `FakeMessagesListChatModel` for tool-calling tests) is the canonical seam. It cycles through a list of responses, so a multi-step agent can be driven deterministically.

```python
from langchain_core.messages import AIMessage, ToolCall
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel

fake = FakeMessagesListChatModel(
    responses=[
        AIMessage(
            content="",
            tool_calls=[ToolCall(name="search", args={"query": "berlin weather"}, id="t1")],
        ),
        AIMessage(content="It's 18C and clear."),
    ]
)


def test_agent_calls_search_then_responds() -> None:
    agent = create_tool_calling_agent(fake, tools=[search], prompt=prompt)
    executor = AgentExecutor(agent=agent, tools=[search])
    out = executor.invoke({"input": "weather in Berlin?"})
    assert "18C" in out["output"]
```

For callback assertions (did the agent invoke a specific tool? in what order?), capture events through `astream_events` in a test fixture and assert on the kinds — `on_tool_start` + `on_chain_end` are usually enough. See [`../cross-cutting/testing-strategy.md`](../cross-cutting/testing-strategy.md) for the three-tier split.

## Anti-patterns

- **Reaching for `langchain.chains.LLMChain` / `ConversationChain`.** Deprecated since 0.2 and removed from agent-friendly surfaces in 0.3. Use `prompt | llm` (LCEL) for one-shot calls and `AgentExecutor` for tool loops.
- **Shoehorning a multi-agent flow into one `AgentExecutor`.** A single executor with a giant tool list collapses into "the model chooses badly". Move to [LangGraph](langgraph.md) the moment you need supervisor → worker delegation, parallel fan-out, or explicit state.
- **Skipping `max_iterations`.** Without it, a confused model can loop a single tool until it hits the model's context window. Set it.
- **Returning rich objects from tools.** Tools should return strings or JSON-serializable dicts. Anything else gets coerced by LangChain to `repr()` and the model sees gibberish.
- **Setting `temperature > 0` for the agent model.** Tool-use accuracy collapses past about 0.3. Keep deterministic; use a separate non-zero-temperature call for any creative final-answer step.
- **Mixing message-history backends mid-session.** `RunnableWithMessageHistory` keys by `session_id`; if you swap backends without migrating, the agent's prior turns disappear silently.

## Composition matrix

How the patterns in [`../patterns/`](../patterns/) map to LangChain vs LangGraph in this repo:

| Pattern | LangChain | LangGraph | Notes |
|---------|-----------|-----------|-------|
| [ReAct](../patterns/react.md) | `AgentExecutor` + `create_tool_calling_agent` | `create_react_agent()` | LangChain is leaner; LangGraph wins when you want checkpointing |
| [Routing / tool use](../patterns/routing-tool-use.md) | `with_structured_output` + dispatch | Conditional edges from a router node | LangChain wins for single-step routing |
| [RAG](../patterns/rag.md) | Retriever as a tool inside `AgentExecutor` | Retriever node → generator node | LangChain wins unless you need conditional re-retrieve |
| [Prompt chaining](../patterns/prompt-chaining.md) | LCEL: `prompt1 \| llm \| parser \| prompt2 \| llm` | Sequence of nodes | LangChain (LCEL) wins for linear chains |
| [Parallel calls](../patterns/parallel-calls.md) | `RunnableParallel` or `asyncio.gather` | Fan-out node | Either; LangChain simpler for small fans |
| [Plan-execute-reflect](../patterns/plan-execute-reflect.md) | Awkward — no state | Built-in state graph | **Use LangGraph** |
| [Multi-agent (flat)](../patterns/multi-agent-flat.md) | Awkward — peer messaging by hand | [CrewAI](crewai.md) is the better fit | Don't force into LangChain |
| [Multi-agent (hierarchical)](../patterns/multi-agent-hierarchical.md) | Awkward — no supervisor abstraction | `langgraph-supervisor` | **Use LangGraph** |
| [Event-driven](../patterns/event-driven.md) | Wrap executor in your own consumer loop | Explicit graph per event | LangGraph wins; the per-event state machine is exactly what it's for |
| [Memory](../patterns/memory.md) | `RunnableWithMessageHistory` + backend | Checkpointer + state | LangChain for plain chat history; LangGraph when memory crosses runs |

## MCP integration

LangChain (post-0.3) uses `langchain-mcp-adapters` — the same package as LangGraph. Tools surface as `BaseTool` instances and plug into `create_tool_calling_agent` + `AgentExecutor`.

**Streamable HTTP transport (the `mcp.tavily` capability):**

```python
import os
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

client = MultiServerMCPClient({
    "tavily": {
        "transport": "streamable_http",
        "url": "https://mcp.tavily.com/mcp/",
        "headers": {"Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}"},
    },
})
tools = await client.get_tools()

llm = ChatAnthropic(model="claude-sonnet-4-6")
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a research assistant."),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])
agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, max_iterations=5)

result = await executor.ainvoke({"input": "Compare GraphQL vs gRPC for streaming workloads."})
print(result["output"])
```

**Stdio transport:** identical shape with `"transport": "stdio"` and a `"command"` / `"args"` config instead of `url`.

For richer graph orchestration over the same tool set, prefer LangGraph's `create_react_agent` (see [`langgraph.md`](langgraph.md)).

## Version notes

One-line summary: 0.3.x consolidated agents under `langchain.agents`; earlier versions split between `langchain` and `langchain-experimental`. `>=0.4` may break the `@tool` decorator surface — pin tight. (Matches frontmatter `versions.notes`.)

| Version | Status | Notes |
|---------|--------|-------|
| `< 0.3.0` | Known incompatible | `langchain.agents` lived split across `langchain` and `langchain-experimental`. `initialize_agent` was the documented loop, not `create_tool_calling_agent`. Recipes that target the consolidated 0.3.x surface won't import. |
| `0.3.0 – 0.3.18` | Recommended | Last validated against the [agent minimal example](#minimal-agent) and [memory](#memory) sections in this doc. `last_known_good: "0.3.18"` per frontmatter. |
| `0.3.19+` | Untested-on-paper | Likely fine — 0.3.x has stayed source-compatible since the consolidation — but CI does not validate. Re-verify the [streaming](#streaming) `astream_events(version="v2")` shape before adopting. |
| `>=0.4.0` | Likely incompatible | The `@tool` decorator surface is signaled to change in the 0.4 line. Treat as a re-port, not a bump. |

### Upgrade gotchas

- **`langchain-anthropic >=0.2.0`.** Required to expose `ChatAnthropic.bind_tools` with strict-schema support. Pinned in the frontmatter. Below 0.2 the binder silently relaxes the tool schema and the model improvises arguments.
- **`langchain-core >=0.3.0`.** The runnable + messages protocol must match the `langchain` major. Mixing `langchain-core 0.2.x` with `langchain 0.3.x` is a frequent silent-fail source (tool-call protocol drift in `AIMessage.tool_calls`).
- **`langchain.chains.LLMChain` and `ConversationChain`.** Deprecated in 0.2, removed from the agent-friendly surface in 0.3. Already called out in [Anti-patterns](#anti-patterns); replace with LCEL (`prompt | llm`) for one-shot calls and `AgentExecutor` for tool loops.
- **`astream_events(version="v1")`.** Deprecated. The v1 event names differ from v2; mixing them in one consumer loop yields silent missing-event drops. Set `version="v2"` per the [Streaming](#streaming) section.

### Why these bounds

The `0.3.0` floor is the version that consolidated `langchain.agents` and removed the `langchain-experimental` split. Before 0.3 the import paths shifted often enough that pinned recipes broke between minors; after 0.3 the surface has held source-compatible. The `last_known_good: "0.3.18"` upper marker is the most recent minor we've validated the [minimal agent](#minimal-agent) and [memory](#memory) examples against. The forward-looking note about `>=0.4` is conservative: the LangChain team has signaled that the `@tool` decorator surface will change, so treat a 0.4 bump as a porting exercise, not a `package.json` edit.
