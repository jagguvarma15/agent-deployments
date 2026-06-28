---
blueprints_version: 7420e28
applies_to:
  pattern: prompt-chaining
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

# Stack suggestion: Prompt Chaining

Linear N-step pipeline shape — each step's output is the next step's input, with optional validation gates between steps. Pattern fits content generation, document transformation, multi-stage drafting workflows.

## Recommended picks (default mode)

| Slot | Pick | Why |
|---|---|---|
| Framework | `vercel_ai_sdk` (TS) / `pydantic_ai` (Py) | `generateText` chains naturally; structured output validation at each gate. |
| LLM | `stack/llm-claude` (Sonnet 4.6) | Quality-per-token sweet spot for multi-step generation. |
| Relational | `relational.postgres` | Per-pipeline-run state for restart-from-failure semantics. |
| Cache | `cache.redis` | Step-output cache when steps are idempotent; rate limits. |
| Tracing | `obs.langfuse` | One span per chain step; chain-level trace aggregates all. |
| Eval | `eval.promptfoo` | Cases assert on chain output shape and quality. |

## Local-only swaps

- **`stack/llm-claude` → `stack/llm-local-vllm`** — quality scales gracefully with step count for vLLM-served 70B AWQ.

## See also

- [`docs/recipes/content-pipeline.md`](../../recipes/content-pipeline.md) — recipe shipping this combo
- [`patterns/prompt-chaining/overview.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/patterns/prompt-chaining/overview.md) — pattern overview
