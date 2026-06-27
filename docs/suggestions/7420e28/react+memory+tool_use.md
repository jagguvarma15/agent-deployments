---
blueprints_version: 7420e28
applies_to:
  pattern: react
  primitives: [memory, tool_use]
  modifiers: []
recommends:
  framework: pydantic_ai
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
  memory_store: memory_store.zep
  guardrail: null
  embedding: embedding.openai
  rerank: null
local_only_swaps:
  - {from: stack/llm-claude, to: stack/llm-local-vllm}
est_tokens: 650
---

# Stack suggestion: ReAct + Memory + Tool Use

Personal-assistant shape — a single agent that remembers across sessions, recalls previous conversations semantically, and uses tools (look up files, fetch context). Memory lifts a one-shot research bot into a continuing assistant.

## Recommended picks (default mode)

| Slot | Pick | Why |
|---|---|---|
| Framework | `pydantic_ai` (Py) / `vercel_ai_sdk` (TS) | Same agentic surface as plain ReAct; tool surface stays small. |
| LLM | `stack/llm-claude` (Sonnet 4.6) | Conversational continuity benefits from Sonnet over Haiku. |
| Relational | `relational.postgres` | Backs Zep's session/user store. |
| Cache | `cache.redis` | Session cache + rate limits. |
| Memory store | `memory_store.zep` | Per-user/session memory with built-in summarization and semantic search. |
| Embeddings | `embedding.openai` | 1536-dim `text-embedding-3-small`; Zep's vector index defaults. |
| Tracing | `obs.langfuse` | Captures the memory-recall step alongside LLM calls. |
| Eval | `eval.promptfoo` | Multi-turn cases verify recall correctness. |

## Local-only swaps

- **`stack/llm-claude` → `stack/llm-local-vllm`** — same trade as plain ReAct.
- **Memory + embeddings stay on Zep + OpenAI** — no fully-local embeddings capability is wired yet; plan to add `embedding.local-bge` (BGE-M3 under TEI) in a follow-up.

## See also

- [`docs/recipes/memory-assistant.md`](../../recipes/memory-assistant.md) — the recipe shipping this combo
- [`primitives/memory/overview.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/primitives/memory/overview.md) — memory primitive
- [`docs/capabilities/memory_store/zep.md`](../../capabilities/memory_store/zep.md) — Zep wiring
