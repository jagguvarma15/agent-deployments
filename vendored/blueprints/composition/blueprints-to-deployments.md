# Blueprints → Deployments

A reader who finishes a pattern doc has a question: *which production-shaped agent uses this?* This page answers it.

It's the agent-blueprints-side companion to [`agent-deployments/docs/blueprint-map.md`](https://github.com/jagguvarma15/agent-deployments/blob/main/docs/blueprint-map.md), which goes the other direction (recipe → pattern). Keep both pages open if you're orienting for the first time.

## How to read this

`agent-blueprints` covers *cognitive* shape — how the agent thinks. `agent-deployments` covers *operational* shape — how the agent survives production (auth, rate limiting, retries, idempotency, observability, tracing). Every deployment recipe inherits the operational layer; each one picks from this repo via the **three-tier taxonomy**:

```
recipe declares:
  agent_pattern: <one>         # the flow shape (from patterns/)
  primitives: [...]            # building blocks the agent uses (from primitives/)
  modifiers: [...]             # transformations layered on the pattern (from modifiers/)
  capabilities: [...]          # deployment provisioning (managed by agent-deployments)
```

The first three come from this repo (cognitive). The fourth is owned by agent-deployments (operational). A recipe picks exactly one pattern + zero or more primitives + zero or more modifiers + zero or more capabilities.

This page is the index of which recipes use which cognitive units. For the canonical recipe-to-pattern table with deployment links, see the [agent-deployments blueprint map](https://github.com/jagguvarma15/agent-deployments/blob/main/docs/blueprint-map.md).

## Reverse lookup: which deployments use what?

### Patterns (flow shapes)

| Pattern | Used by deployment recipe(s) as the `agent_pattern:` |
|---------|------------------------------|
| [Prompt Chaining](../patterns/prompt-chaining/overview.md) | `content-pipeline` |
| [Parallel Calls](../patterns/parallel-calls/overview.md) | `parallel-enricher` |
| [Orchestrator-Worker](../patterns/orchestrator-worker/overview.md) | (composed inside `code-review-agent`, `hierarchical-agent`) |
| [Evaluator-Optimizer](../patterns/evaluator-optimizer/overview.md) | `content-pipeline` |
| [ReAct](../patterns/react/overview.md) | `research-assistant`, `claude-code-subagent` |
| [Plan & Execute](../patterns/plan_and_execute/overview.md) | `code-review-agent` |
| [RAG](../patterns/rag/overview.md) | `docs-rag-qa` |
| [Reflection](../patterns/reflection/overview.md) | `code-review-agent` |
| [Routing](../patterns/routing/overview.md) | `customer-support-triage` |
| [Multi-Agent](../patterns/multi_agent/overview.md) | `ops-crew`, `hierarchical-agent`, `restaurant-rebooking` |
| [Event-Driven](../patterns/event_driven/overview.md) | `restaurant-rebooking` |
| [Saga](../patterns/saga/overview.md) | (no current recipe — candidate for booking/order workflows) |

### Primitives (building blocks)

| Primitive | Used by deployment recipe(s) as a `primitives[]` entry |
|---------|------------------------------|
| [Tool Use](../primitives/tool_use/overview.md) | Almost every recipe — it's the default. |
| [Memory](../primitives/memory/overview.md) | `memory-assistant`, `research-assistant`, `ops-crew`, `restaurant-rebooking` |
| [Skills](../primitives/skills/overview.md) | `memory-assistant`, `claude-code-subagent` |

### Modifiers (transforms)

| Modifier | Used by deployment recipe(s) as a `modifiers[]` entry |
|---------|------------------------------|
| [Human in the Loop](../modifiers/human_in_the_loop/overview.md) | (no current recipe — candidate for content moderation, code-review approval flows) |

Entries marked "no current recipe" are documented here but don't yet have a production-shaped example in `agent-deployments`. That's a contribution opportunity — see [agent-deployments contributing guide](https://github.com/jagguvarma15/agent-deployments/blob/main/CONTRIBUTING.md).

## Per-framework code variants

Pattern code lives under `patterns/<name>/code/<lang>/<framework>/` — see [`meta/style-guide.md`](../meta/style-guide.md#code-layout) for the convention. `_reference.py` next to those directories holds the framework-agnostic MockLLM reference the design docs read against. When `agent-scaffold` resolves a recipe that targets a specific framework, its context assembler prefers the matching variant (e.g. a `langgraph` recipe loads `patterns/<name>/code/python/langgraph/<name>.py`) over the generic reference. ReAct is the current exemplar of the layout; other patterns follow in per-pattern PRs.

## What every deployment inherits

The cognitive/operational boundary isn't decorative — it's load-bearing. Each pattern's design doc should be silent on these concerns; each deployment recipe must be explicit about them. The table below lists what `agent-deployments` always provides, so you know what you're not reading about in this repo.

| Concern | Where it's documented |
|---------|----------------------|
| Auth (JWT, API keys) | [`agent-deployments/docs/cross-cutting/auth-jwt.md`](https://github.com/jagguvarma15/agent-deployments/blob/main/docs/cross-cutting/auth-jwt.md) |
| Rate limiting | [`agent-deployments/docs/cross-cutting/rate-limiting.md`](https://github.com/jagguvarma15/agent-deployments/blob/main/docs/cross-cutting/rate-limiting.md) |
| Structured logging | [`agent-deployments/docs/cross-cutting/logging-structured.md`](https://github.com/jagguvarma15/agent-deployments/blob/main/docs/cross-cutting/logging-structured.md) |
| Observability + tracing | [`agent-deployments/docs/cross-cutting/observability.md`](https://github.com/jagguvarma15/agent-deployments/blob/main/docs/cross-cutting/observability.md) |
| Idempotency | [`agent-deployments/docs/cross-cutting/idempotency.md`](https://github.com/jagguvarma15/agent-deployments/blob/main/docs/cross-cutting/idempotency.md) |
| Testing strategy | [`agent-deployments/docs/cross-cutting/testing-strategy.md`](https://github.com/jagguvarma15/agent-deployments/blob/main/docs/cross-cutting/testing-strategy.md) |
| Capability provisioning (vector DBs, queues, dashboards, etc.) | [`agent-deployments/docs/capabilities/`](https://github.com/jagguvarma15/agent-deployments/tree/main/docs/capabilities) |

See [system-design-heritage](../foundations/system-design-heritage.md) for the long-form explanation of why these concerns live there and not here.

## Picking a starting point

If you know the **shape of the problem** but not the agent:

1. Use [Choosing a Pattern](../foundations/choosing-a-pattern.md) to land on a pattern.
2. Find your pattern in the table above, jump to the matching recipe.
3. If no recipe exists, the pattern still ships with `overview` → `design` → `implementation` + reference code; the deployment recipe is the missing layer you'd add for production.

If you know the **product feature** but not the architecture:

1. Skim the recipe list in [`agent-deployments/docs/recipes/`](https://github.com/jagguvarma15/agent-deployments/tree/main/docs/recipes) — they're named by intent (e.g. `customer-support-triage`, `docs-rag-qa`).
2. Open the closest recipe; its `Composes:` section names the patterns it builds on.
3. Read those patterns here before extending the recipe.

## Next step

Walk through the full lifecycle on one concrete example: [Blueprint → Spec → Scaffold](./blueprint-to-spec-to-scaffold.md).
