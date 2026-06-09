# Cost & Latency: Reflection

All figures are rough estimates based on a frontier-tier model at approximately
$3/1M input tokens and $15/1M output tokens. Reflection has a similar cost structure
to Evaluator-Optimizer but typically uses slightly more tokens per iteration because
self-critiques tend to be richer than structured rubric scores.

---

## At a Glance

|                          | Typical (P50 estimate)      | High end (P95 estimate)                |
|--------------------------|-----------------------------|----------------------------------------|
| LLM calls per request    | ~4 (2 iters x 2 calls)     | ~9 (3 iters x 3 calls)                 |
| Total input tokens       | ~2,500 - 6,000              | ~10,000+                               |
| Total output tokens      | ~800 - 2,500                | ~5,000+                                |
| Latency                  | ~3 - 6s                     | ~7 - 12s                               |
| Cost per 1,000 requests  | ~$2.50 - $6.00              | ~$10 - $22                             |

Relative cost tier: Medium to High. Each iteration adds 2-3 LLM calls. The break-even
point vs a single high-quality prompt is roughly 1.5 iterations. Beyond that, Reflection
costs more than a single well-crafted prompt and should only be used when the quality
improvement justifies it.

---

## Call Breakdown (per iteration)

| Call          | Purpose                                        | Est. input tokens | Est. output tokens |
|---------------|------------------------------------------------|-------------------|--------------------|
| Generate      | Produce candidate draft                        | 300 - 900         | 200 - 700          |
| Critique      | Self-assess draft against criteria             | 500 - 1,500       | 80 - 300           |
| Revise        | Improve draft based on critique (if not pass)  | 400 - 1,000       | 200 - 700          |

The critique call's input = the full generated draft + criteria. A long draft means
an expensive critique call. This is where Reflection gets more expensive than
Evaluator-Optimizer — critique prompts are typically more open-ended and produce
richer (longer) output.

---

## Latency Profile

All calls within each iteration are sequential. There is no parallelism in the
standard Reflection loop.

Per-iteration latency breakdown:
- Generate: ~500 - 1,200ms
- Critique: ~400 - 800ms
- Revise (if needed): ~500 - 1,000ms

P50 estimate (2 iterations): ~3 - 6s
P95 estimate (3 iterations, verbose generate): ~7 - 12s

---

## What Drives Cost Up

- Number of iterations. The primary driver. Each iteration adds 2-3 LLM calls.
  A task that consistently needs 3 iterations costs ~50% more than one that needs 2.
- Draft length. The critique receives the full draft as input. A 600-token draft makes
  the critique call ~600 tokens more expensive than a 50-token draft.
- Revise input context. If the revise call includes the original task, full prior draft,
  and full critique, the context grows rapidly. Only the improvement instruction needs
  to be passed.
- Verbose critique output. An open-ended critique prompt produces longer critiques
  (reasoning, examples, suggestions). This costs more output tokens and adds more
  tokens to the revise call's input.

---

## What Drives Latency Up

- Iteration count (additive sequential latency)
- Long draft generation (many output tokens)
- Detailed critique generation (many output tokens before the VERDICT line)

---

## Cost Control Knobs

Keep the critique structured. A critique that starts with VERDICT/ISSUES/SUGGESTION
terminates faster and produces shorter output than an open-ended prose critique.
Structured output typically reduces critique token output by 50-70%.

Pass only the improvement instruction to the revise call, not the full prior draft.
The LLM can generate a fresh response from the task + instruction without needing
the verbatim previous attempt.

Add a pass condition check before running the revise call. If the critique says
VERDICT: pass, stop immediately and return the current draft. Do not run a revise
call. This sounds obvious but is easy to miss in implementation.

Use max_iterations=2 by default. For most tasks, the quality gain from iteration 3
is marginal relative to the cost. Reserve max_iterations=3 for high-stakes outputs.

Make the criteria specific and limited. 2-3 concrete criteria converge faster than
5-8 vague ones. "Under 200 words" and "includes a code example" are criteria the
critic can check definitively. "High quality" is not.

---

## Comparison to Related Patterns

| Pattern               | Est. LLM calls      | Est. cost tier    | Est. latency | Best when                                       |
|-----------------------|---------------------|-------------------|--------------|-------------------------------------------------|
| Reflection            | 2-3 per iteration  | Medium to High     | High         | Self-critique without a separate evaluator      |
| Evaluator-Optimizer   | 2-3 per iteration  | Medium to High     | High         | Structured rubric, possibly different evaluator |
| Prompt Chaining       | N (fixed)          | Low                | Medium       | Quality acceptable in a single pass             |
