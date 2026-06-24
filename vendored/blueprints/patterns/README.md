# Patterns

Patterns are **flow shapes** — control structures with a beginning, middle, and end. This directory holds **<!-- AUTO:count cohort=patterns -->14<!-- /AUTO --> patterns** split by who controls the flow:

- **Agent patterns** (`category: agent`) — the LLM decides what to do next at each step. ReAct, RAG, Multi-Agent, etc.
- **Workflows** (`category: workflow`) — the developer's code defines the flow; the LLM fills in the content at each step. Prompt Chaining, Parallel Calls, etc.

Both kinds describe the same *type* of thing (a control-flow shape), which is why they live in the same directory with a `category` discriminator. Workflows are the foundation agent patterns evolve from — each agent pattern's `evolution.md` traces the bridge.

For the other two cohorts in the three-tier taxonomy, see:
- [`../primitives/`](../primitives/) — building blocks the agent uses (tool use, memory, skills).
- [`../modifiers/`](../modifiers/) — transformations layered on a pattern (human-in-the-loop).

Pick your shape in [`../foundations/choosing-a-pattern.md`](../foundations/choosing-a-pattern.md).

## Workflows

Code-controlled flow shapes. The developer defines the structure; the LLM fills in content at each step.

<!-- AUTO:cohort-table cohort=patterns filter=category:workflow style=tiers base=../ -->
| Pattern | What It Does | Overview | Design | Implementation |
|---|---|---|---|---|
| **Evaluator-Optimizer** | Generate-evaluate feedback loop that iteratively improves output. | [overview](../patterns/evaluator-optimizer/overview.md) | [design](../patterns/evaluator-optimizer/design.md) | [impl](../patterns/evaluator-optimizer/implementation.md) |
| **Orchestrator-Worker** | LLM decomposes a task and delegates to specialized workers. | [overview](../patterns/orchestrator-worker/overview.md) | [design](../patterns/orchestrator-worker/design.md) | [impl](../patterns/orchestrator-worker/implementation.md) |
| **Parallel Calls** | Concurrent LLM calls on independent inputs, aggregated at the end. | [overview](../patterns/parallel-calls/overview.md) | [design](../patterns/parallel-calls/design.md) | [impl](../patterns/parallel-calls/implementation.md) |
| **Prompt Chaining** | Sequential LLM calls with validation gates between steps. | [overview](../patterns/prompt-chaining/overview.md) | [design](../patterns/prompt-chaining/design.md) | [impl](../patterns/prompt-chaining/implementation.md) |
<!-- /AUTO -->

## Agent patterns

LLM-controlled flow shapes. The developer provides tools and constraints; the LLM decides what to do.

<!-- AUTO:cohort-table cohort=patterns filter=category:agent style=tiers base=../ -->
| Pattern | What It Does | Evolves From | Overview | Design | Implementation |
|---|---|---|---|---|---|
| **Agentic RAG** | RAG where the agent plans retrievals, decomposes queries, routes across sources, reflects on sufficiency, and enforces citation-bound answers. | RAG, Plan & Execute | [overview](../patterns/agentic_rag/overview.md) | [design](../patterns/agentic_rag/design.md) | [impl](../patterns/agentic_rag/implementation.md) |
| **Event-Driven** | Agents triggered by queue or stream events rather than HTTP requests. | Tool Use | [overview](../patterns/event_driven/overview.md) | [design](../patterns/event_driven/design.md) | [impl](../patterns/event_driven/implementation.md) |
| **Long-Horizon** | Multi-session agent tasks that span hours to weeks; checkpoint-and-resume across crashes, deploys, and external waits. | Saga, Event-Driven | [overview](../patterns/long_horizon/overview.md) | [design](../patterns/long_horizon/design.md) | [impl](../patterns/long_horizon/implementation.md) |
| **Multi-Agent** | Supervisor-worker delegation across multiple autonomous agents. | Orchestrator-Worker, Routing | [overview](../patterns/multi_agent/overview.md) | [design](../patterns/multi_agent/design.md) | [impl](../patterns/multi_agent/implementation.md) |
| **Plan & Execute** | LLM creates a full plan upfront, then executes each step sequentially. | Orchestrator-Worker | [overview](../patterns/plan_and_execute/overview.md) | [design](../patterns/plan_and_execute/design.md) | [impl](../patterns/plan_and_execute/implementation.md) |
| **RAG** | Retrieval-augmented generation: retrieve relevant context before generating. | Parallel Calls | [overview](../patterns/rag/overview.md) | [design](../patterns/rag/design.md) | [impl](../patterns/rag/implementation.md) |
| **ReAct** | Reason-act loop: the LLM reasons, calls a tool, observes, and repeats until done. | Prompt Chaining | [overview](../patterns/react/overview.md) | [design](../patterns/react/design.md) | [impl](../patterns/react/implementation.md) |
| **Reflection** | LLM critiques its own output and self-improves through structured feedback. | Evaluator-Optimizer | [overview](../patterns/reflection/overview.md) | [design](../patterns/reflection/design.md) | [impl](../patterns/reflection/implementation.md) |
| **Routing** | Intent classification dispatches inputs to specialized handlers. | Parallel Calls | [overview](../patterns/routing/overview.md) | [design](../patterns/routing/design.md) | [impl](../patterns/routing/implementation.md) |
| **Saga** | Long-running, multi-step business processes that need compensation when an intermediate step fails. | Tool Use, Prompt Chaining | [overview](../patterns/saga/overview.md) | [design](../patterns/saga/design.md) | [impl](../patterns/saga/implementation.md) |
<!-- /AUTO -->

## Reading order

If you're new to patterns, start with **ReAct** — the simplest agent shape and the most foundational. Every other agent pattern builds on top of it.

For the other two cohorts (primitives + modifiers), read their respective README pages once you've internalized at least one pattern.

## Documentation tiers

Each pattern (agent or workflow) ships with three levels of documentation:

- **`overview.md`** (Tier 1) — What it does, when to use it, architecture diagram. Start here.
- **`design.md`** (Tier 2) — Component breakdown, data flow, error handling, scaling.
- **`implementation.md`** (Tier 3) — Pseudocode, interfaces, state management, testing strategy.

Most patterns also ship with `evolution.md` (the bridge from the workflow it evolved from), `observability.md` (metrics, traces, failure signatures), and `cost-and-latency.md` (token budgets, latency profile, cost control knobs).
