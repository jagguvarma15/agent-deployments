# Cohere

> Rerank for RAG retrieval. Used by `rerank.cohere`.

**Signup**: https://dashboard.cohere.com

## Create a key

1. Sign in at https://dashboard.cohere.com.
2. **API Keys** → **Create Trial Key** (or production key once you have billing). Name it.
3. Copy the key — shown once. Trial keys are rate-limited but free; production keys remove the cap.

## Wire into your project

```bash
agent-scaffold auth login --provider cohere
# Or:
export COHERE_API_KEY='...'
```

Declare `capabilities: [rerank.cohere]` in the recipe. The scaffold inserts a rerank step in the retrieval pipeline: top-50 vector hits → Cohere rerank → top-5 to LLM context.

## Verify

```bash
curl -sS -X POST https://api.cohere.com/v2/rerank \
  -H "Authorization: Bearer $COHERE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"rerank-v3.5","query":"smoke","documents":["doc a","doc b"]}' \
  | head -20
```

Should return a `results` array with relevance scores.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401` | Trial key / wrong workspace | Recreate at https://dashboard.cohere.com |
| `429` | Trial rate limit | Upgrade to production key |
| `model not found` | Cohere rotated model id | Check https://docs.cohere.com/docs/rerank-overview; update capability frontmatter |
| Reranked results worse than raw | Query / doc lang mismatch | v3.5 is multilingual but pin model to a Cohere version that matches your locale |

## See also

- [`docs/capabilities/rerank/cohere.md`](../capabilities/rerank/cohere.md) — capability definition.
- [`patterns/agentic_rag/overview.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/patterns/agentic_rag/overview.md) — typical consumer pattern.
