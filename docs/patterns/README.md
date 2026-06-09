# Patterns

> **This directory was retired.** Pattern docs now live in the vendored snapshot of agent-blueprints at [`../../vendored/blueprints/patterns/`](../../vendored/blueprints/patterns/) (and [`../../vendored/blueprints/workflows/`](../../vendored/blueprints/workflows/) for workflow-shaped patterns). The lighter mirror that previously lived here has been deleted in favor of vendoring the canonical content directly.
>
> Pattern ids use the **underscore** form (matches upstream blueprints): `event_driven`, `multi_agent`, `plan_and_execute`, `tool_use`, `human_in_the_loop`, `react`, `rag`, `memory`, `reflection`, `routing`, `saga`. Workflow ids use **hyphen** form: `prompt-chaining`, `parallel-calls`, `orchestrator-worker`, `evaluator-optimizer`. See [`MANIFEST_SCHEMA.md`](../../MANIFEST_SCHEMA.md#naming-canon).

## Where to find each pattern

| Pattern | Where it lives now |
|---|---|
| RAG | [`../../vendored/blueprints/patterns/rag/`](../../vendored/blueprints/patterns/rag/) |
| ReAct | [`../../vendored/blueprints/patterns/react/`](../../vendored/blueprints/patterns/react/) |
| Tool Use | [`../../vendored/blueprints/patterns/tool_use/`](../../vendored/blueprints/patterns/tool_use/) |
| Routing | [`../../vendored/blueprints/patterns/routing/`](../../vendored/blueprints/patterns/routing/) |
| Memory | [`../../vendored/blueprints/patterns/memory/`](../../vendored/blueprints/patterns/memory/) |
| Plan & Execute | [`../../vendored/blueprints/patterns/plan_and_execute/`](../../vendored/blueprints/patterns/plan_and_execute/) |
| Reflection | [`../../vendored/blueprints/patterns/reflection/`](../../vendored/blueprints/patterns/reflection/) |
| Multi-Agent (flat + hierarchical) | [`../../vendored/blueprints/patterns/multi_agent/`](../../vendored/blueprints/patterns/multi_agent/) |
| Event-Driven | [`../../vendored/blueprints/patterns/event_driven/`](../../vendored/blueprints/patterns/event_driven/) |
| Saga | [`../../vendored/blueprints/patterns/saga/`](../../vendored/blueprints/patterns/saga/) |
| Human-in-the-Loop | [`../../vendored/blueprints/patterns/human_in_the_loop/`](../../vendored/blueprints/patterns/human_in_the_loop/) |
| Prompt Chaining (workflow) | [`../../vendored/blueprints/workflows/prompt-chaining/`](../../vendored/blueprints/workflows/prompt-chaining/) |
| Parallel Calls (workflow) | [`../../vendored/blueprints/workflows/parallel-calls/`](../../vendored/blueprints/workflows/parallel-calls/) |
| Orchestrator-Worker (workflow) | [`../../vendored/blueprints/workflows/orchestrator-worker/`](../../vendored/blueprints/workflows/orchestrator-worker/) |
| Evaluator-Optimizer (workflow) | [`../../vendored/blueprints/workflows/evaluator-optimizer/`](../../vendored/blueprints/workflows/evaluator-optimizer/) |

Each pattern ships six tier files: `overview.md` (Tier 1), `design.md` (Tier 2), `implementation.md` (Tier 3), `evolution.md`, `observability.md`, `cost-and-latency.md`.

For machine-readable consumers, the [`catalog.yaml`](../../catalog.yaml) embeds the full pattern index in its `patterns[]` / `workflows[]` / `compositions[]` blocks (sourced from upstream `patterns-catalog.yaml`).

## Decision flow

For "how do I pick a pattern?", read [`../../vendored/blueprints/foundations/choosing-a-pattern.md`](../../vendored/blueprints/foundations/choosing-a-pattern.md) (the upstream decision flowchart).
