# Agent Patterns

Agent patterns are architectures where **the LLM controls the flow**. Unlike [workflows](../workflows/README.md) where the developer defines the execution path, agents decide at runtime which tools to call, when to continue, and when to stop.

Every agent pattern in this section builds on one or more [workflow patterns](../workflows/README.md). Each includes an `evolution.md` document that traces the bridge from workflow to agent — showing exactly what changes when you hand control to the LLM.

## Why Agents?

Workflows break down when:
- You can't enumerate the steps in advance
- The right action depends on what the LLM discovers during execution
- Your conditional branching logic becomes unmanageable
- The task requires adaptive, exploratory behavior

Agents solve this by letting the LLM reason about the next step dynamically. The tradeoff: you gain flexibility at the cost of predictability, testability, and cost control.

## The Eleven Agent Patterns

```mermaid
graph TD
    subgraph "Single-Agent Patterns"
        ReAct[ReAct<br/>Reason + Act loop]
        ToolUse[Tool Use<br/>Function calling]
        Memory[Memory<br/>Persistent state]
        RAG[RAG<br/>Retrieval-augmented]
        Reflection[Reflection<br/>Self-critique]
        Routing[Routing<br/>Intent dispatch]
        PlanExec[Plan & Execute<br/>Strategy + execution]
    end
    subgraph "Multi-Agent Patterns"
        MultiAgent[Multi-Agent<br/>Delegation + supervision]
    end
    subgraph "Operational Patterns"
        EventDriven[Event-Driven<br/>Queue/stream triggered]
        Saga[Saga<br/>Compensation on failure]
        HITL[Human in the Loop<br/>Approval gate]
    end

    ToolUse -.->|"adds reasoning loop"| ReAct
    ReAct -.->|"adds planning"| PlanExec
    ReAct -.->|"adds retrieval"| RAG
    ReAct -.->|"adds self-critique"| Reflection
    ReAct -.->|"adds persistence"| Memory
    Routing -.->|"adds delegation"| MultiAgent
    PlanExec -.->|"adds multi-agent"| MultiAgent
    ToolUse -.->|"adds event source"| EventDriven
    ToolUse -.->|"adds compensation"| Saga
    ToolUse -.->|"adds approval gate"| HITL

    style ReAct fill:#fff3e0
    style ToolUse fill:#fff3e0
    style Memory fill:#fff3e0
    style RAG fill:#fff3e0
    style Reflection fill:#fff3e0
    style Routing fill:#fff3e0
    style PlanExec fill:#fff3e0
    style MultiAgent fill:#fce4ec
    style EventDriven fill:#fff3e0
    style Saga fill:#fff3e0
    style HITL fill:#fff3e0
```

| Pattern | Complexity | Evolves From (Workflow) | Best For |
|---------|-----------|----------------------|----------|
| [ReAct](./react/overview.md) | Intermediate | Prompt Chaining | Open-ended tasks with tool use |
| [Tool Use](./tool_use/overview.md) | Beginner | Prompt Chaining | Structured function calling |
| [Memory](./memory/overview.md) | Intermediate | Prompt Chaining | Multi-session context |
| [RAG](./rag/overview.md) | Intermediate | Parallel Calls | Knowledge-grounded generation |
| [Reflection](./reflection/overview.md) | Intermediate | Evaluator-Optimizer | Self-improving output |
| [Routing](./routing/overview.md) | Beginner | Parallel Calls | Intent-based dispatch |
| [Plan & Execute](./plan_and_execute/overview.md) | Intermediate | Orchestrator-Worker | Complex multi-step tasks |
| [Multi-Agent](./multi_agent/overview.md) | Advanced | Orchestrator-Worker + Routing | Collaborative task solving |
| [Event-Driven](./event_driven/overview.md) | Advanced | Tool Use | Async reactive systems on a queue or stream |
| [Saga](./saga/overview.md) | Advanced | Tool Use + Prompt Chaining | Long-running multi-step processes with compensation |
| [Human in the Loop](./human_in_the_loop/overview.md) | Intermediate | Tool Use | High-stakes actions requiring approval |

## Reading Order

If you're new to agent patterns, start with **ReAct** — it's the simplest and most foundational. From there:

1. **[ReAct](./react/overview.md)** — The core agent loop. Every other pattern builds on this.
2. **[Tool Use](./tool_use/overview.md)** — How agents interact with external systems.
3. **[RAG](./rag/overview.md)** — Adding external knowledge to agent reasoning.
4. **[Memory](./memory/overview.md)** — Persisting context across conversations.
5. **[Reflection](./reflection/overview.md)** — Self-critique for higher quality output.
6. **[Routing](./routing/overview.md)** — Directing inputs to specialized handlers.
7. **[Plan & Execute](./plan_and_execute/overview.md)** — Strategic planning before execution.
8. **[Multi-Agent](./multi_agent/overview.md)** — Multiple agents collaborating.
9. **[Event-Driven](./event_driven/overview.md)** — Agents triggered by queue/stream events instead of synchronous requests.
10. **[Saga](./saga/overview.md)** — Long-running, multi-step processes that need compensation when an intermediate step fails.
11. **[Human in the Loop](./human_in_the_loop/overview.md)** — Gating high-stakes actions behind human approval.

## Documentation Tiers

Each pattern has three levels of documentation:

- **overview.md** (Tier 1) — What it does, when to use it, architecture diagram. Start here.
- **design.md** (Tier 2) — Component breakdown, data flow, error handling, scaling.
- **implementation.md** (Tier 3) — Pseudocode, interfaces, state management, testing strategy.
- **evolution.md** — How this pattern evolves from its parent workflow pattern.

Most patterns also ship with **observability.md** (metrics, traces, failure signatures) and **cost-and-latency.md** (token budgets, latency profile, cost control knobs).
