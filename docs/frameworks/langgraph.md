---
id: langgraph
language: python
package: langgraph
versions:
  minimum: "0.3.21"
---

# Framework: LangGraph

**Language:** Python
**Install:** `uv add langgraph`
**Version pinned:** 0.3.21

## Core abstractions

- **StateGraph:** A directed graph where nodes are functions and edges are transitions. State flows through the graph as a typed dict.
- **State:** A TypedDict (or Pydantic model) that accumulates data as the graph executes. Each node receives the full state and returns updates.
- **Nodes:** Python functions (sync or async) that take state, do work (call LLM, run tool, transform data), and return state updates.
- **Edges:** Transitions between nodes. Can be unconditional (always go A -> B) or conditional (router function picks the next node based on state).
- **Checkpointer:** Persists state between steps, enabling resume, replay, and human-in-the-loop. Postgres-backed in production.
- **ToolNode:** Built-in node that executes tool calls from a preceding LLM node. Handles tool schemas, invocation, and result injection.

## Patterns it supports well

- **RAG** -- Retriever node -> generator node with state carrying retrieved chunks. Add conditional edges for multi-step retrieval.
- **ReAct** -- `create_react_agent()` gives you a prebuilt reason-act-observe loop with tool execution. The canonical use case.
- **Plan & Execute** -- Planner node produces a step list in state, executor node works through them, reflector node evaluates and optionally re-plans.
- **Multi-Agent (hierarchical)** -- `langgraph-supervisor` package provides a supervisor node that delegates to sub-graphs. Each sub-agent is its own compiled graph.
- **Memory** -- Checkpointer + state persistence means conversation history and memory are first-class.

## Event-driven state machine

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

### Conditional branches per decision type

When `act` should differ by decision type, replace the straight edge with a conditional router:

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

### Why not just call the LLM directly without a graph?

For a single event you could. The graph pays off when:

- **Retries are per-node, not per-event.** A failure in `act` shouldn't re-run `enrich`. Build the retry boundary into the graph.
- **Observability matters.** LangGraph's tracing logs each node entry/exit — easy to correlate with the event ID in your logger context.
- **You want checkpointing.** Pausing mid-event for human-in-the-loop (e.g. high-stakes notifications requiring approval) is one line: add a `Checkpointer`.

## Patterns where it's awkward

- **Simple tool use / routing** -- If your agent is just "classify intent, call one tool," LangGraph's graph abstraction is overkill. Use Pydantic AI instead.
- **Parallel fan-out** -- LangGraph supports map-reduce via `Send()`, but the ergonomics are heavier than raw `asyncio.gather()` with Pydantic AI.

## Idiomatic minimal example

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

## Strengths

- **State management** is the best in class. TypedDict state + checkpointing means you can pause, resume, replay, and branch agent execution.
- **Observability** via LangSmith integration -- every node execution, LLM call, and tool invocation is traced automatically.
- **Composition** -- sub-graphs can be compiled and used as nodes in parent graphs, enabling hierarchical agent architectures.
- **Production-proven** -- widely deployed, well-documented, active maintenance.

## Trade-offs

- **Learning curve** -- the graph mental model takes time. Simple agents feel over-engineered.
- **LangChain coupling** -- while LangGraph is technically separate, it works best with LangChain's model wrappers (`ChatAnthropic`, `ChatOpenAI`), tool decorators, and message types.
- **Async complexity** -- async graph execution works but debugging is harder than sync Pydantic AI agents.
- **Verbose for simple cases** -- a 3-node graph with conditional edges is more code than a Pydantic AI agent with a tool.

## Used in this repo

| Prototype | Role |
|-----------|------|
| `docs-rag-qa` | Listed as LangGraph in README, but implementation uses Pydantic AI for simplicity. LangGraph would be the choice for multi-step RAG with state. |
| `research-assistant` | Listed for ReAct loop. The `create_react_agent` helper is the natural fit. |
| `code-review-agent` | Plan & Execute pattern -- planner + executor + reflector as graph nodes. (Skeleton) |
| `memory-assistant` | Checkpointer-backed memory with LangGraph + mem0. (Skeleton) |
| `hierarchical-agent` | `langgraph-supervisor` for hierarchical multi-agent. (Skeleton) |

## Reference implementations

- [recipes/docs-rag-qa.md](../recipes/docs-rag-qa.md) -- RAG pipeline (design-level LangGraph, implemented with Pydantic AI)
- [recipes/research-assistant.md](../recipes/research-assistant.md) -- ReAct agent
- [recipes/code-review-agent.md](../recipes/code-review-agent.md) -- Plan & Execute (skeleton)
- [recipes/hierarchical-agent.md](../recipes/hierarchical-agent.md) -- Hierarchical multi-agent (skeleton)
