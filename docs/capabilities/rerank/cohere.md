---
id: rerank.cohere
kind: rerank
layer: agent
provides: [search_result_reranking]
env_vars: [COHERE_API_KEY]
model: rerank-v3.5
docker: null
probe: cohere_rerank_ping
bootstrap_step: null
provisioning_time: instant
cost_tier: per-call
est_tokens: 500
card:
  name: Cohere Rerank v3.5
  description: "Late-stage rerank step that re-orders retrieval results by relevance to the query."
  capabilities_provided: [search_result_reranking, multilingual_rerank]
  required_credentials: [COHERE_API_KEY]
emit_files: []
docs: |
  Cohere Rerank v3.5 — plugs into RAG recipes between vector search and the
  LLM prompt to lift recall@5 by 20-40 points on benchmark datasets.
---

# Capability: rerank.cohere

> First-run setup: [`getting-started/cohere.md`](../../getting-started/cohere.md). Vendor: https://docs.cohere.com/docs/rerank-overview.

**Used for:** Improving RAG retrieval quality by reranking top-k vector hits with a dedicated relevance model.

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

## Client integration

**Python (cohere):**

```python
from cohere import AsyncClient

client = AsyncClient(api_key=os.environ["COHERE_API_KEY"])

# After vector search returns top-50 hits:
response = await client.rerank(
    model="rerank-v3.5",
    query="streaming GraphQL APIs",
    documents=[hit["content"] for hit in vector_hits],
    top_n=5,
)

# Map back to the original metadata
top5 = [vector_hits[r.index] for r in response.results]
```

**TypeScript (cohere-ai):**

```ts
import { CohereClient } from "cohere-ai";

const client = new CohereClient({ token: process.env.COHERE_API_KEY! });

const response = await client.v2.rerank({
  model: "rerank-v3.5",
  query: "streaming GraphQL APIs",
  documents: vectorHits.map((h) => h.content),
  topN: 5,
});

const top5 = response.results.map((r) => vectorHits[r.index]);
```

## Probe

`cohere_rerank_ping` reranks `["doc a", "doc b"]` against the query `"smoke"` and asserts the response shape.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 Unauthorized` | Trial key / wrong workspace | Recreate at https://dashboard.cohere.com |
| `429 Too Many Requests` | Trial rate limit | Upgrade to production key, or add backoff |
| `model not found` | Cohere rotated model id | Check https://docs.cohere.com/docs/rerank-overview; update the capability's model reference |
| Reranked results worse than raw | Query/doc lang mismatch | v3.5 is multilingual but pin model to a Cohere version matching your locale |

## See also

- [`vendored/blueprints/patterns/agentic_rag/overview.md`](../../../vendored/blueprints/patterns/agentic_rag/overview.md) — primary consumer pattern
- [`capabilities/vector_db/qdrant.md`](../vector_db/qdrant.md) — typical upstream of the rerank step
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
