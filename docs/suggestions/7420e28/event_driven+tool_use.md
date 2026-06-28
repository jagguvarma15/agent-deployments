---
blueprints_version: 7420e28
applies_to:
  pattern: event_driven
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
  queue: queue.redis-streams
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
  - {from: queue.redis-streams, to: queue.kafka}
est_tokens: 650
---

# Stack suggestion: Event-Driven + Tool Use

Agent triggered by queue or stream events rather than HTTP requests. Fits reservation rebooking, transactional workflows, async batch processing.

## Recommended picks (default mode)

| Slot | Pick | Why |
|---|---|---|
| Framework | `langgraph` | Per-event workflow state benefits from LangGraph's checkpointer. |
| LLM | `stack/llm-claude` (Haiku for intake/eligibility, Sonnet for substantive steps) | Mixed tier matches per-role cost / quality trade-off. |
| Queue | `queue.redis-streams` | Sufficient for ≤10k events/sec; piggybacks on existing Redis. |
| Relational | `relational.postgres` | Idempotency store + per-event state. |
| Cache | `cache.redis` | Already present for streams; also rate limits. |
| Tracing | `obs.langfuse` | Per-event trace, span per role. |
| Eval | `eval.promptfoo` | Policy-decision cases (rebook eligibility, intent classification). |

## Local-only swaps

- **`stack/llm-claude` → `stack/llm-local-vllm`** — works well; per-event cost drops to GPU electricity.
- **`queue.redis-streams` → `queue.kafka`** — for sustained throughput >10k events/sec/topic or days-of-retention requirements.

## See also

- [`docs/recipes/restaurant-rebooking.md`](../../recipes/restaurant-rebooking.md) — recipe shipping this combo
- [`patterns/event_driven/overview.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/patterns/event_driven/overview.md)
- [`docs/capabilities/queue/redis-streams.md`](../../capabilities/queue/redis-streams.md), [`docs/capabilities/queue/kafka.md`](../../capabilities/queue/kafka.md)
