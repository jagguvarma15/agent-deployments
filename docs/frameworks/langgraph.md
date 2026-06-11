---
id: langgraph
language: python
package: langgraph
versions:
  minimum: "0.3.21"
  last_known_good: "0.3.21"
  notes: "0.3.x is the recipe-validated floor; pin tight because the checkpointer + prebuilt agent surface still shifts between minors."
---

# Framework: LangGraph

**Language:** Python
**Install:** `uv add langgraph`
**Version pinned:** 0.3.21

## When to choose LangGraph

LangGraph is the right fit when an agent needs explicit state, multi-step orchestration, or a graph mental model — a planner / executor / reflector loop, an event-driven enrich → decide → act pipeline, or a hierarchical supervisor delegating to sub-graphs. State management is the best in class: TypedDict state plus checkpointing means you can pause, resume, replay, and branch agent execution. Observability via LangSmith integration is automatic — every node execution, LLM call, and tool invocation is traced. Composition is a first-class concern: sub-graphs compile and slot into parent graphs as nodes, enabling hierarchical architectures. Production-proven, widely deployed, active maintenance.

Core abstractions:

- **StateGraph:** A directed graph where nodes are functions and edges are transitions. State flows through the graph as a typed dict.
- **State:** A TypedDict (or Pydantic model) that accumulates data as the graph executes. Each node receives the full state and returns updates.
- **Nodes:** Python functions (sync or async) that take state, do work (call LLM, run tool, transform data), and return state updates.
- **Edges:** Transitions between nodes. Can be unconditional (always go A -> B) or conditional (router function picks the next node based on state).
- **Checkpointer:** Persists state between steps, enabling resume, replay, and human-in-the-loop. Postgres-backed in production.
- **ToolNode:** Built-in node that executes tool calls from a preceding LLM node. Handles tool schemas, invocation, and result injection.

## Minimal agent

```python
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool

@tool
def search(query: str) -> str:
    """Search the web."""
    return f"Results for: {query}"

llm = ChatAnthropic(model="claude-sonnet-4-6-20250514")
agent = create_react_agent(llm, tools=[search])

# Run
result = agent.invoke({"messages": [("user", "What is MCP?")]})
print(result["messages"][-1].content)
```

## Tools

LangGraph reuses LangChain's tool surface: decorate a Python callable with `@tool` (from `langchain_core.tools`) and the docstring + parameter annotations become the schema the model sees. The prebuilt `create_react_agent` wires tools into a ReAct loop automatically; for hand-rolled graphs, `ToolNode` is the canonical node type that consumes the LLM node's emitted tool calls, dispatches them, and folds results back into state. Tool failures surface as messages in state so the next LLM turn can react.

## Structured output

For typed responses, use LangChain's `with_structured_output(SchemaClass)` against a Pydantic model. The bound LLM returns instances of `SchemaClass` directly; LangGraph nodes that need a typed decision (e.g. a router picking the next branch) call the bound model and write the result into state. Structured-output calls participate in LangSmith tracing alongside regular LLM calls.

## Memory

Memory is built into the graph: state persists across nodes within an invocation, and the `Checkpointer` persists state across invocations. Postgres-backed checkpointer is the production shape; an in-memory one is fine for local dev. Conversation history is just a list in state — the prebuilt `MessagesState` typed-dict shortcut handles append semantics. Long-term memory layers on top: store retrieval results, summarized history, or per-user facts in state and load them in the entry node.

## Streaming

`compiled_graph.astream()` yields state-delta dicts as the graph executes — each node entry produces a streaming event. `astream_events()` opens a finer-grained stream including LLM token deltas and tool call events. Both compose with FastAPI's `StreamingResponse` for HTTP transport.

## Observability

LangSmith integration is the default: set `LANGSMITH_API_KEY` and every node execution, LLM call, and tool invocation is traced automatically. Trace IDs propagate through `astream` events so a frontend can correlate streamed output back to the underlying graph trace. For OpenTelemetry, wrap node functions with the standard `tracer.start_as_current_span` decorator; LangGraph doesn't interfere with the OTel context.

## Retrieval

LangGraph treats retrieval as a node-shape concern, not a first-class primitive: a `retrieve` node calls a `Retriever` (the LangChain interface) and writes results into state, then a `generate` node consumes them. For RAG pipelines, see [`../patterns/rag.md`](../patterns/rag.md); the LangChain doc covers the `Retriever` interface and ingestion patterns that pair with LangGraph nodes.

## Anti-patterns

- **Simple tool use / routing** — If your agent is just "classify intent, call one tool," LangGraph's graph abstraction is overkill. Use Pydantic AI instead.
- **Parallel fan-out** — LangGraph supports map-reduce via `Send()`, but the ergonomics are heavier than raw `asyncio.gather()` with Pydantic AI.
- **Learning curve cost vs. payoff.** The graph mental model takes time. Simple agents feel over-engineered. Reach for LangGraph when state + checkpointing + composition are load-bearing.
- **LangChain coupling.** While LangGraph is technically separate, it works best with LangChain's model wrappers (`ChatAnthropic`, `ChatOpenAI`), tool decorators, and message types. Treat them as a pair, not orthogonal choices.
- **Async complexity.** Async graph execution works but debugging is harder than sync Pydantic AI agents. Prefer sync where state-graph shape allows.
- **Verbose for simple cases.** A 3-node graph with conditional edges is more code than a Pydantic AI agent with a tool.

## Composition matrix

LangGraph slots cleanly into the patterns the repo documents:

- **RAG** — Retriever node → generator node with state carrying retrieved chunks. Add conditional edges for multi-step retrieval.
- **ReAct** — `create_react_agent()` gives you a prebuilt reason-act-observe loop with tool execution. The canonical use case.
- **Plan & Execute** — Planner node produces a step list in state, executor node works through them, reflector node evaluates and optionally re-plans.
- **Multi-Agent (hierarchical)** — `langgraph-supervisor` package provides a supervisor node that delegates to sub-graphs. Each sub-agent is its own compiled graph.
- **Memory** — Checkpointer + state persistence means conversation history and memory are first-class.

### Event-driven state machine

LangGraph's explicit graph model maps cleanly onto event-driven agent lifecycles: each event flows through a fixed sequence of nodes (enrich → decide → act → persist → emit), with conditional branches for different decision types. The graph is built once and reused per event; per-event state is the dict passed to `ainvoke`.

This is **not** what `create_react_agent` gives you — that's a request/response ReAct loop. For event-driven agents, build the graph yourself:

```python
from langgraph.graph import END, StateGraph

async def enrich(state: dict) -> dict:
    state["context"] = await fetch_world_state(state["event"])
    return state

async def decide(state: dict) -> dict:
    # Structured-output LLM call bound to your decision schema
    state["decision"] = await llm_decide(state["event"], state["context"])
    return state

async def act(state: dict) -> dict:
    # Idempotent tool calls keyed on state["event"].event_id
    await execute(state["decision"], idempotency_key=state["event"].event_id)
    return state

async def persist_and_emit(state: dict) -> dict:
    await write_outcome(state)
    await emit_outcome_event(state)
    return state

def build_graph():
    g = StateGraph(dict)
    g.add_node("enrich", enrich)
    g.add_node("decide", decide)
    g.add_node("act", act)
    g.add_node("persist", persist_and_emit)
    g.set_entry_point("enrich")
    g.add_edge("enrich", "decide")
    g.add_edge("decide", "act")
    g.add_edge("act", "persist")
    g.add_edge("persist", END)
    return g.compile()
```

The consumer loop sits outside the graph: it pulls events from a stream/queue (Redis Streams, Kafka, SQS), invokes `compiled_graph.ainvoke({"event": event})` per event, and handles ACK / DLQ. See [Event-Driven Agents pattern](../patterns/event-driven.md) for the full lifecycle, and [restaurant-rebooking](../recipes/restaurant-rebooking.md) for a worked example.

Conditional branches per decision type — when `act` should differ by decision type, replace the straight edge with a conditional router:

```python
def route_by_decision(state: dict) -> str:
    return state["decision"].action.value  # e.g. "fill_from_waitlist", "no_action"

g.add_conditional_edges(
    "decide",
    route_by_decision,
    {
        "fill_from_waitlist": "act_fill",
        "offer_alternative_time": "act_offer",
        "notify_host_only": "act_notify_host",
        "no_action": "persist",  # skip act entirely
    },
)
```

Why a graph at all for a single event? For one event you could call the LLM directly. The graph pays off when:

- **Retries are per-node, not per-event.** A failure in `act` shouldn't re-run `enrich`. Build the retry boundary into the graph.
- **Observability matters.** LangGraph's tracing logs each node entry/exit — easy to correlate with the event ID in your logger context.
- **You want checkpointing.** Pausing mid-event for human-in-the-loop (e.g. high-stakes notifications requiring approval) is one line: add a `Checkpointer`.

## MCP integration

LangGraph integrates MCP via `langchain-mcp-adapters`. MCP-discovered tools convert to LangChain tool objects and load into a `ToolNode` or a prebuilt ReAct agent.

**Streamable HTTP transport (the `mcp.tavily` capability):**

```python
import os
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic

client = MultiServerMCPClient({
    "tavily": {
        "transport": "streamable_http",
        "url": "https://mcp.tavily.com/mcp/",
        "headers": {"Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}"},
    },
})

tools = await client.get_tools()

llm = ChatAnthropic(model="claude-sonnet-4-6")
agent = create_react_agent(llm, tools)

result = await agent.ainvoke({"messages": [
    {"role": "user", "content": "Compare GraphQL vs gRPC for streaming workloads."}
]})
print(result["messages"][-1].content)
```

**Wiring tools into a custom graph (when prebuilt isn't enough):**

```python
from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition

graph = StateGraph(MessagesState)
graph.add_node("agent", llm.bind_tools(tools))
graph.add_node("tools", ToolNode(tools))
graph.add_conditional_edges("agent", tools_condition)
graph.add_edge("tools", "agent")
graph.set_entry_point("agent")
compiled = graph.compile()
```

Multi-server setups list each server in `MultiServerMCPClient({...})`; `get_tools()` flattens all discovered tools across servers.

## Version notes

0.3.x is the recipe-validated floor; pin tight because the checkpointer + prebuilt agent surface still shifts between minors.

| Version | Status | Notes |
|---------|--------|-------|
| `< 0.3.0` | Unsupported | Pre-stable checkpointer interface; `create_react_agent` import path differs. Recipes assume the post-0.3 layout. |
| `0.3.21+` | Recommended | Current pin in the frontmatter. Validated against [`../recipes/research-assistant.md`](../recipes/research-assistant.md) and the hierarchical / code-review skeletons. |
| `0.4+` | Untested | May work; CI does not validate. Re-verify checkpointer + `langgraph-supervisor` compatibility before bumping. |

### Upgrade gotchas

- **`create_react_agent` import path.** Lives under `langgraph.prebuilt` in 0.3.x. Older code that imported from `langgraph.prebuilt.chat_agent_executor` will break; newer code that imports from a moved-again path on `0.4` will break in the other direction. Pin `0.3.x` and re-verify the import shape on bump.
- **`langgraph-supervisor` is on its own semver.** The hierarchical recipe ([`../recipes/hierarchical-agent.md`](../recipes/hierarchical-agent.md)) depends on it as a separate package; check both pins together when planning a LangGraph bump.
- **Checkpointer connection-string format.** Postgres checkpointer parses the URL itself; using `psycopg`-style vs `asyncpg`-style URIs interchangeably is a frequent silent-fail. The recipe code uses the docs' canonical shape.

### Why these bounds

The `0.3.21` floor is the version that ships the stabilized `StateGraph` + `ToolNode` + `create_react_agent` surface every recipe in this repo exercises. Pre-0.3 the prebuilt agent layered on a different state contract; recipes that rely on the post-0.3 `MessagesState` typed-dict shortcut won't run. The reason there is no recorded upper bound is conservative: LangGraph's release cadence is fast enough that "last_known_good" would drift between sessions; treat anything past `0.3.x` as "test before you ship".

## Used in this repo

| Prototype | Role |
|-----------|------|
| `docs-rag-qa` | Listed as LangGraph in README, but implementation uses Pydantic AI for simplicity. LangGraph would be the choice for multi-step RAG with state. |
| `research-assistant` | Listed for ReAct loop. The `create_react_agent` helper is the natural fit. |
| `code-review-agent` | Plan & Execute pattern -- planner + executor + reflector as graph nodes. (Skeleton) |
| `memory-assistant` | Checkpointer-backed memory with LangGraph + mem0. (Skeleton) |
| `hierarchical-agent` | `langgraph-supervisor` for hierarchical multi-agent. (Skeleton) |

Reference implementations:

- [recipes/docs-rag-qa.md](../recipes/docs-rag-qa.md) — RAG pipeline (design-level LangGraph, implemented with Pydantic AI)
- [recipes/research-assistant.md](../recipes/research-assistant.md) — ReAct agent
- [recipes/code-review-agent.md](../recipes/code-review-agent.md) — Plan & Execute (skeleton)
- [recipes/hierarchical-agent.md](../recipes/hierarchical-agent.md) — Hierarchical multi-agent (skeleton)
