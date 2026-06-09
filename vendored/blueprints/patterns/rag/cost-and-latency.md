# Cost & Latency: RAG

All figures are rough estimates based on a frontier-tier model at approximately
$3/1M input tokens and $15/1M output tokens. Embedding costs are excluded from LLM
cost estimates but add a small per-query overhead.

---

## At a Glance

|                          | Typical (P50 estimate) | High end (P95 estimate)               |
|--------------------------|------------------------|---------------------------------------|
| LLM calls per query      | ~1 (generate)          | ~2 (if reranker is an LLM call)       |
| Embedding calls          | ~1 (query embed)       | ~2 (query + hypothetical doc embed)   |
| Total input tokens       | ~1,000 - 3,000         | ~6,000+ (many large chunks)           |
| Total output tokens      | ~100 - 500             | ~1,000+                               |
| Latency per query        | ~0.8 - 2s              | ~2 - 5s                               |
| Cost per 1,000 queries   | ~$0.80 - $3.00         | ~$5 - $12                             |

Relative cost tier: Low to Medium. The query path (embed + retrieve + generate) has a
fixed call structure with no loops. It is one of the most cost-predictable agent patterns.

---

## Call Breakdown (query path)

| Call              | Purpose                               | Est. input tokens | Est. output tokens |
|-------------------|---------------------------------------|-------------------|--------------------|
| Embed query       | Convert question to vector (not LLM)  | N/A               | N/A                |
| Vector search     | Find top-k relevant chunks (not LLM)  | N/A               | N/A                |
| Rerank (optional) | Re-score chunks for relevance         | 200 - 600         | 20 - 100           |
| Generate answer   | Produce grounded response             | 800 - 3,000+      | 100 - 500          |

The generate call is where most of the LLM cost lives. Its input = system prompt +
retrieved chunks + user question. With top_k=3 and chunks of 500 tokens each,
the context is already ~1,800 tokens before the question.

---

## Call Breakdown (ingestion path, offline)

| Call              | Purpose                               | Est. input tokens | Est. output tokens |
|-------------------|---------------------------------------|-------------------|--------------------|
| Embed chunk       | Convert each chunk to vector          | 50 - 500 per chunk| N/A                |

Ingestion is typically a one-time or batched background cost, not a per-query cost.
For a 100-page document split into 300 chunks, a single ingestion run costs roughly
the same as 300 embedding API calls. This is paid once, not per user query.

---

## Latency Profile

Query path latency breakdown:
- Embed query: ~10 - 50ms (hosted embedding API)
- Vector search: ~20 - 200ms (depends on index size and similarity library)
- Rerank (if used): ~200 - 500ms
- Generate answer: ~500 - 2,000ms (grows with context size)

P50 estimate: ~0.8 - 2s
P95 estimate: ~2 - 5s (large chunks, slow vector search at scale, long answer)

RAG is the lowest-latency knowledge-grounded pattern because the query path has no
loops and a fixed number of LLM calls.

---

## What Drives Cost Up

- Chunk size. Larger chunks mean more input tokens per retrieved chunk. A top_k=3 query
  with 1,000-token chunks adds 3,000 tokens of context; the same query with 300-token
  chunks adds 900 tokens.
- top_k value. Each additional retrieved chunk adds its full token count to the
  generate call's input. Retrieving 6 chunks instead of 3 can increase generate
  input cost by 50-100%.
- Answer verbosity. Long generated answers cost more output tokens. If the use case
  allows short answers, add a length constraint.
- Re-embedding on every query. Embedding the same query repeatedly (e.g., retries,
  identical questions from different users) wastes embedding calls. Cache embeddings
  for recent or frequent queries.

---

## What Drives Latency Up

- Vector index size. Searching a 10M-vector index is slower than searching a 10K-vector
  index. Approximate nearest-neighbor indexing (HNSW, IVF) is essential at scale.
- Large chunks in generate context. 3 chunks of 1,000 tokens each means the LLM
  must process 3,000 tokens of context before generating a single output token.
- Embedding API latency. If you use a hosted embedding API, its latency adds to each
  query. Self-hosted embedding with a fast model can cut this to under 10ms.

---

## Cost Control Knobs

Reduce chunk size and increase top_k slightly. Smaller chunks (300-400 tokens) with
top_k=4 retrieve more targeted context than large chunks (1,000 tokens) with top_k=3,
while using similar total input tokens and giving the reranker more to work with.

Add a relevance threshold. If the top retrieved chunk has a similarity score below
a threshold (e.g., 0.6 on cosine similarity), return "I don't have information on
that" rather than generating from irrelevant context. This saves the generate call
entirely for out-of-scope questions.

Cache question embeddings. Questions are often similar or identical across users.
A simple exact-match cache on the question string, or an embedding cache with a
similarity threshold, can skip the embedding call entirely for repeated questions.

Use a cheaper model for short, factual answers. RAG answers are grounded in retrieved
context, which means the model needs to extract and paraphrase rather than reason.
Cheaper models often perform comparably for straightforward factual Q&A.

Limit answer length. Add "Respond in under 150 words" to the generation prompt for
use cases where a concise answer is acceptable. Output tokens are ~5x more expensive
per token than input tokens.

---

## Comparison to Related Patterns

| Pattern     | Est. LLM calls | Est. cost tier | Est. latency | Best when                                       |
|-------------|----------------|----------------|--------------|--------------------------------------------------|
| RAG         | ~1-2 (fixed)   | Low to Medium  | Low          | Knowledge-grounded Q&A, no multi-step reasoning |
| ReAct       | 3-10+ (dynamic)| Medium, high var| Variable    | Multi-step reasoning, tool use alongside retrieval|
| Memory      | 2-3 per turn   | Medium         | Medium       | Personalization, cross-session context           |
