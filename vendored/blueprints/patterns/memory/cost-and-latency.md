# Cost & Latency: Memory Agent

All figures are rough estimates based on a frontier-tier model at approximately
$3/1M input tokens and $15/1M output tokens. Memory adds overhead to every turn
but the cost per turn is relatively stable and predictable.

---

## At a Glance

|                          | Typical (P50 estimate) | High end (P95 estimate)                 |
|--------------------------|------------------------|-----------------------------------------|
| LLM calls per turn       | ~2 - 3                 | ~3 (retrieve, generate, extract)        |
| Total input tokens/turn  | ~800 - 3,000           | ~6,000+ (long history, many memories)  |
| Total output tokens/turn | ~100 - 500             | ~1,000+                                 |
| Latency per turn         | ~1 - 3s                | ~4 - 7s                                 |
| Cost per 1,000 turns     | ~$1.00 - $4.00         | ~$8 - $20                               |

Relative cost tier: Medium. Each turn is more expensive than a plain LLM call due to
retrieval, history, and extraction overhead. Over a 10-turn conversation, the cumulative
cost is significant.

---

## Call Breakdown (per turn)

| Call             | Purpose                                   | Est. input tokens | Est. output tokens |
|------------------|-------------------------------------------|-------------------|--------------------|
| Retrieve         | Search long-term store (not LLM)          | N/A               | N/A                |
| Generate         | Produce response with memory context      | 400 - 2,000+      | 100 - 500          |
| Extract          | Identify facts to store from the exchange | 200 - 600         | 20 - 100           |

The generate call's input grows with two things: the working memory (conversation history)
and the retrieved memories injected as context. Both expand as the session continues.

Working memory growth estimate (per additional turn kept):
- Each extra turn in working memory adds approximately 200-500 tokens to the generate
  call's input. A 20-turn history can add 4,000-10,000 tokens to each call.

---

## Latency Profile

Per-turn latency breakdown:
- Retrieval (long-term store lookup): ~10 - 50ms (fast key-value) or ~20 - 200ms (vector search)
- Generate call: ~500 - 2,000ms (grows with history length)
- Extract call: ~300 - 700ms

P50 estimate: ~1 - 3s per turn
P95 estimate: ~4 - 7s (long session, vector search, large history)

Extraction can be made asynchronous. If you do not need to wait for extraction to
complete before returning the response to the user, the user-visible latency is just
the retrieve + generate time.

---

## What Drives Cost Up

- Session length. Working memory accumulates across turns. If all 20 prior turns
  are kept in context, each new turn pays for all 20 turns of prior history in input tokens.
  This is the primary cost driver in long sessions.
- Memory retrieval quality. If retrieval returns too many results (high top_k), or if
  the retrieved memories are verbose, the generate call's context grows unnecessarily.
- Extraction frequency. Running extraction on every turn, including trivial turns
  ("OK thanks", "got it"), wastes a full LLM call on turns that produce no useful facts.
- Semantic search (vector store). Embedding each user message and searching a vector
  store adds latency and, if you're using a hosted embedding API, a small per-call cost.

---

## What Drives Latency Up

- Working memory size (longer history = more input tokens = slower generation)
- Vector store search latency (especially at scale with large indexes)
- Synchronous extraction (if the user waits for extraction before receiving the response)

---

## Cost Control Knobs

Cap working memory at 10-15 turns. Beyond that, maintain a running summary of older
turns rather than keeping them verbatim. Summarizing 20 old turns into a 200-token
"session summary" can reduce generate input tokens by 3,000+.

Skip extraction on trivial turns. Only run extraction when the user message contains
a noun phrase or assertion likely to be a persistent fact. A simple heuristic (message
length > 30 words, or contains phrases like "I prefer", "I use", "my project is") is
enough to skip ~40% of extraction calls with minimal fact loss.

Limit retrieval results. Set top_k to 3 or fewer for long-term store lookups. Retrieving
5+ memories per turn inflates generate input without proportional quality gain.

Run extraction asynchronously. The user-visible response does not need to wait for
fact extraction. Fire the extraction call after returning the response and write to
the store in the background.

Use a cheaper model for extraction. Fact extraction from a short text exchange is a
mechanical structured-output task. A smaller, cheaper model does it reliably.

---

## Comparison to Related Patterns

| Pattern     | Est. LLM calls/turn | Est. cost tier | Est. latency | Best when                                     |
|-------------|---------------------|----------------|--------------|-----------------------------------------------|
| Memory      | 2-3                 | Medium         | Medium       | Multi-session continuity, personalization     |
| RAG         | 2 (fixed)           | Low to Medium  | Low to Medium| Document retrieval per query, no session state|
| Tool Use    | 2 per round         | Low to Medium  | Low          | Structured actions, no cross-session memory   |
