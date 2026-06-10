---
id: rerank.cohere
kind: rerank
provides: [search_result_reranking]
env_vars: [COHERE_API_KEY]
model: rerank-v3.5
docker: null
probe: cohere_rerank_ping
bootstrap_step: null
emit_files: []
docs: |
  Cohere Rerank v3.5 — late-stage rerank step that re-orders retrieval
  results by relevance to the query. Plugs into RAG recipes between vector
  search and the LLM prompt. Recipes wire it via `capabilities: [rerank.cohere]`;
  the scaffold emits a rerank step in the retrieval pipeline.
---

# Capability: rerank.cohere

> First-run setup: [`getting-started/cohere.md`](../../getting-started/cohere.md). Vendor: https://docs.cohere.com/docs/rerank-overview.

**Used for:** Improving RAG retrieval quality by reranking top-k vector hits with a dedicated relevance model.

## Why pick this

Vector search is fast but coarse; rerank is slow but precise. Putting rerank between retrieval and generation typically lifts recall@5 by 20-40 points on benchmark datasets — biggest win for agentic_rag recipes whose answers depend on getting the right passage to the LLM.

Cohere's hosted rerank is the strongest commercial option; v3.5 is multilingual and handles longer contexts than v2. Self-hosted alternative: `rerank.bge-reranker-v2` (planned, TEI-served).

## Wiring

```yaml
# In a recipe's frontmatter:
capabilities:
  - rerank.cohere
```

The scaffold inserts a rerank step in the retrieval pipeline: vector search returns top 50 → Cohere rerank trims to top 5 → those go to the LLM context.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `COHERE_API_KEY` | *(prompted)* | Cohere API key — stored via keyring |

## Probe

`cohere_rerank_ping` reranks `["doc a", "doc b"]` against the query `"smoke"` and asserts the response shape.

## When to swap it

- **→ `rerank.bge-reranker-v2`** — self-hosted under TEI.
- **→ `rerank.voyage-rerank-2`** — Voyage AI's offering.
- **Skip rerank** — for low-stakes RAG, raw vector search may be enough.

## See also

- [`vendored/blueprints/patterns/agentic_rag/overview.md`](../../../vendored/blueprints/patterns/agentic_rag/overview.md) — primary consumer pattern.
- [`vector_db/qdrant.md`](../vector_db/qdrant.md) — typical upstream of the rerank step.
