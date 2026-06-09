# Cost & Latency: Parallel Calls

All figures are rough estimates based on a frontier-tier model at approximately
$3/1M input tokens and $15/1M output tokens. Actual numbers depend on branch count,
output verbosity, and the aggregation step's complexity.

---

## At a Glance

|                          | Typical (P50 estimate) | High end (P95 estimate)        |
|--------------------------|------------------------|--------------------------------|
| LLM calls per request    | N branches + 1 agg.    | Same, but one branch is slow   |
| Total input tokens       | ~1,200 - 3,000         | ~6,000+                        |
| Total output tokens      | ~600 - 2,000           | ~4,000+                        |
| Latency                  | ~1 - 2.5s              | ~3 - 6s                        |
| Cost per 1,000 requests  | ~$1.00 - $4.00         | ~$6 - $15                      |

Relative cost tier: Medium. You pay for N+1 LLM calls, but wall-clock latency is low
because branches run concurrently. Cost grows linearly with branch count; latency does not.

---

## Call Breakdown

| Call           | Purpose                          | Est. input tokens | Est. output tokens |
|----------------|----------------------------------|-------------------|--------------------|
| Branch 1 to N  | Process each independent chunk   | 200 - 600 each    | 100 - 400 each     |
| Aggregation    | Combine all branch outputs       | 400 - 2,000       | 150 - 600          |

The aggregation call's input scales with the total output of all branches. With 5 branches
each producing 300 tokens, the aggregation prompt already has ~1,500 tokens of context before
any instructions are added.

---

## Latency Profile

Latency is dominated by the slowest branch, not the average branch.

Rough per-branch estimate: ~400 - 900ms per branch (all running concurrently)
Aggregation estimate: ~500 - 900ms

P50 estimate: max(branch latencies) + aggregation = ~1 - 2.5s
P95 estimate: one outlier branch (larger chunk, rate limit hit) + aggregation = ~3 - 6s

The latency advantage over Prompt Chaining disappears if one branch is consistently
slower than the others (uneven chunk sizes, different models per branch, rate limiting).

---

## What Drives Cost Up

- Branch count. Each additional branch is a full LLM call. Going from 4 branches to 8 branches
  roughly doubles the branch call cost (though latency stays flat if you have enough workers).
- Verbose branch outputs. Each branch output contributes to the aggregation prompt's input.
  4 branches x 500 tokens of output = 2,000 tokens of aggregation input before any prompt text.
- Aggregation model choice. If aggregation uses the most capable model and receives a large
  context, it can cost more than all the branches combined.
- Retry on branch failure. A failed branch that retries adds another full LLM call.

---

## What Drives Latency Up

- Uneven chunk sizes. If one chunk is 5x larger than the others, one branch takes 5x longer
  and sets the total latency. Pre-process chunks to equalize length.
- Rate limits. Firing N requests simultaneously can trigger rate limiting, causing some branches
  to queue rather than run in parallel.
- Aggregation context size. A large aggregation input (many verbose branches) slows the
  final synthesis call.

---

## Cost Control Knobs

Cap branch output length. This is the most important lever. Each branch should produce a
focused summary, not a full document. A 100-token branch output vs a 500-token branch output
reduces aggregation input cost by 80% for a 5-branch call.

Cap branch count. Audit whether all branches are strictly necessary. For many tasks, 3-4
branches provide diminishing returns vs 6-8. Set a maximum in code.

Use a cheaper model for branches when branches are mechanical (summarization,
classification, extraction) and a more capable model only for aggregation.

Add a relevance gate before aggregation. If a branch output is empty or clearly off-topic,
drop it rather than passing it to the aggregation prompt.

Stagger branch dispatch if rate limits are a concern. Add a short delay between launching
branches to spread the burst across time. This slightly increases latency but avoids
rate-limit-induced retries which cost more.

---

## Comparison to Related Patterns

| Pattern             | Est. LLM calls  | Est. cost tier | Est. latency  | Best when                             |
|---------------------|-----------------|----------------|---------------|---------------------------------------|
| Parallel Calls      | N+1             | Medium         | Low           | Independent sub-tasks, latency matters|
| Prompt Chaining     | N (fixed)       | Low            | Medium        | Sequential dependent steps            |
| Orchestrator-Worker | 2+N (dynamic)   | Medium         | Medium        | Dynamic decomposition needed          |
