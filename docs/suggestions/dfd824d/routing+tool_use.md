---
blueprints_version: dfd824d
applies_to:
  pattern: routing
  primitives: [tool_use]
  modifiers: []
recommends:
  framework: langgraph
  llm: stack/llm-claude
  api_layer: stack/api-fastapi
  relational: relational.postgres
  cache: cache.redis
  vector_db: null
  retrieval: null
  queue: null
  obs: obs.langfuse
  eval: eval.promptfoo
  mcp_servers: []
  sandbox: null
  durable: null
  memory_store: null
  guardrail: null
  embedding: null
  rerank: null
local_only_swaps:
  - {from: stack/llm-claude, to: stack/llm-local-vllm}
est_tokens: 550
---

# Stack suggestion: Routing + Tool Use

Triage / dispatch shape — a classifier categorizes the input, then routes to a specialist worker that uses tools to handle the request. Pattern fits customer support, code review classification, intent-to-handler dispatch.

## Recommended picks (default mode)

| Slot | Pick | Why |
|---|---|---|
| Framework | `langgraph` (Py) / `mastra` (TS) | Routing is graph-shaped; LangGraph's conditional edges are first-class. |
| LLM | `stack/llm-claude` (Haiku 4.5 for routing, Sonnet 4.6 for workers) | Cheap-and-fast classification + capable workers. |
| Relational | `relational.postgres` | Session state + per-route audit trail. |
| Cache | `cache.redis` | Rate limit by user/route; routing decision cache. |
| Tracing | `obs.langfuse` | Per-route trace bucketing. |
| Eval | `eval.promptfoo` | Routing-accuracy cases per intent. |

## Local-only swaps

- **`stack/llm-claude` → `stack/llm-local-vllm`** — single vLLM instance serves both classifier and workers. Use Llama 3.1 8B for routing (cheap parallel calls) and 70B for specialists.

## See also

- [`docs/recipes/customer-support-triage.md`](../../recipes/customer-support-triage.md) — the validated recipe shipping this combo
- [`vendored/blueprints/patterns/routing/overview.md`](../../../vendored/blueprints/patterns/routing/overview.md) — pattern overview
- [`docs/frameworks/langgraph.md`](../../frameworks/langgraph.md) — framework
