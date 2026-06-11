---
blueprints_version: dfd824d
applies_to:
  pattern: parallel-calls
  primitives: []
  modifiers: []
recommends:
  framework: vercel_ai_sdk
  llm: stack/llm-claude
  api_layer: stack/api-hono
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
est_tokens: 500
---

# Stack suggestion: Parallel Calls

Concurrent LLM calls on independent inputs, results aggregated at the end. Fits batch enrichment, fan-out classification, parallel scoring.

## Recommended picks (default mode)

| Slot | Pick | Why |
|---|---|---|
| Framework | `vercel_ai_sdk` (TS) / `pydantic_ai` (Py) | `Promise.all` / `asyncio.gather` patterns map directly. |
| LLM | `stack/llm-claude` (Haiku 4.5) | Haiku at parallel-call scale wins on cost. |
| Relational | `relational.postgres` | Batch-job state, per-item results. |
| Cache | `cache.redis` | Result cache (idempotent items); rate limit total concurrency. |
| Tracing | `obs.langfuse` | One span per parallel call, batch-level aggregate trace. |
| Eval | `eval.promptfoo` | Per-item correctness regression. |

## Local-only swaps

- **`stack/llm-claude` → `stack/llm-local-vllm`** — Haiku-class quality is achievable with Llama 3.1 8B at high parallelism on a single L4 GPU.

## See also

- [`docs/recipes/parallel-enricher.md`](../../recipes/parallel-enricher.md) — recipe shipping this combo
- [`vendored/blueprints/patterns/parallel-calls/overview.md`](../../../vendored/blueprints/patterns/parallel-calls/overview.md)
