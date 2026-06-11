---
blueprints_version: dfd824d
applies_to:
  pattern: rag
  primitives: []
  modifiers: []
recommends:
  framework: langgraph
  llm: stack/llm-claude
  api_layer: stack/api-fastapi
  relational: relational.postgres
  cache: cache.redis
  vector_db: vector_db.qdrant
  retrieval: null
  queue: null
  obs: obs.langfuse
  eval: eval.deepeval
  mcp_servers: []
  sandbox: null
  durable: null
  memory_store: null
  guardrail: null
  embedding: embedding.openai
  rerank: rerank.cohere
local_only_swaps:
  - {from: stack/llm-claude, to: stack/llm-local-vllm}
est_tokens: 700
---

# Stack suggestion: RAG (canonical)

Q&A-over-your-docs shape — retrieve relevant passages from a vector store, optionally rerank, then generate a cited answer. Pattern fits documentation assistants, internal-knowledge bots, FAQ automation.

## Recommended picks (default mode)

| Slot | Pick | Why |
|---|---|---|
| Framework | `langgraph` (Py) / `vercel_ai_sdk` (TS) | Linear retrieve → rerank → generate flow benefits from explicit graph nodes; LangGraph's `RetrievalQAChain` heritage. |
| LLM | `stack/llm-claude` (Sonnet 4.6) | Citation-bound generation needs an instruction-following model. |
| Vector DB | `vector_db.qdrant` | Self-hosted, payload filtering, gRPC for batch ingest. |
| Embeddings | `embedding.openai` (text-embedding-3-small, 1536 dim) | Best quality-per-dollar; matches Qdrant default collection size. |
| Rerank | `rerank.cohere` (rerank-v3.5) | +20-40 recall@5 points over raw vector hits. |
| Relational | `relational.postgres` | Document metadata, ingestion pipeline state. |
| Cache | `cache.redis` | Query-result cache (1h TTL); rate limits. |
| Tracing | `obs.langfuse` | Retrieve → rerank → generate spans. |
| Eval | `eval.deepeval` | Faithfulness + answer-relevancy + context-precision metrics. |

## Local-only swaps

- **`stack/llm-claude` → `stack/llm-local-vllm`** — quality drop is most noticeable in citation accuracy; pin to 70B AWQ minimum.
- **Embeddings + rerank stay on SaaS** — local alternatives (BGE-M3 + BGE-reranker) need additional setup; planned for a follow-up.

## See also

- [`docs/recipes/docs-rag-qa.md`](../../recipes/docs-rag-qa.md) — the validated recipe shipping this combo
- [`vendored/blueprints/patterns/rag/overview.md`](../../../vendored/blueprints/patterns/rag/overview.md) — pattern overview
- [`docs/capabilities/vector_db/qdrant.md`](../../capabilities/vector_db/qdrant.md), [`docs/capabilities/rerank/cohere.md`](../../capabilities/rerank/cohere.md)
