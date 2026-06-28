---
blueprints_version: 7420e28
applies_to:
  pattern: plan_and_execute
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
  sandbox: sandbox.e2b
  durable: null
  memory_store: null
  guardrail: null
  embedding: null
  rerank: null
local_only_swaps:
  - {from: stack/llm-claude, to: stack/llm-local-vllm}
est_tokens: 600
---

# Stack suggestion: Plan & Execute + Tool Use

LLM creates a multi-step plan upfront, then executes each step sequentially (re-planning if a step fails). Fits code review, structured analysis, multi-stage diagnostics where the steps emerge from upfront planning.

## Recommended picks (default mode)

| Slot | Pick | Why |
|---|---|---|
| Framework | `langgraph` | Plan-node + per-step executor-node + re-plan loop maps cleanly to LangGraph state. |
| LLM | `stack/llm-claude` (Sonnet 4.6, Opus for planning when complexity is high) | Planning quality dominates outcome; Sonnet is usually enough. |
| Sandbox | `sandbox.e2b` | Run code reproductions or test commands during execution. |
| Relational | `relational.postgres` | Plan + per-step results persisted for resume. |
| Cache | `cache.redis` | Step-output cache; rate limits. |
| Tracing | `obs.langfuse` | Plan node + each execute node as nested spans. |
| Eval | `eval.promptfoo` | Plan-shape regression cases. |

## Local-only swaps

- **`stack/llm-claude` → `stack/llm-local-vllm`** — planning step is the highest-quality-sensitive; pin 70B AWQ.
- **Sandbox stays on E2B** — no fully-local sandbox capability wired yet.

## See also

- [`docs/recipes/code-review-agent.md`](../../recipes/code-review-agent.md) — recipe shipping this combo
- [`patterns/plan_and_execute/overview.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/patterns/plan_and_execute/overview.md)
- [`docs/capabilities/sandbox/e2b.md`](../../capabilities/sandbox/e2b.md)
