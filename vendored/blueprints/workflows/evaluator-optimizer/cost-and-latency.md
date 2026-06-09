# Cost & Latency: Evaluator-Optimizer

All figures are rough estimates based on a frontier-tier model at approximately
$3/1M input tokens and $15/1M output tokens. Actual costs depend heavily on how
many iterations the loop runs before meeting the quality threshold.

---

## At a Glance

|                          | Typical (P50 estimate)     | High end (P95 estimate)               |
|--------------------------|----------------------------|---------------------------------------|
| LLM calls per request    | ~4 (2 iterations x 2 calls)| ~9 (3 iterations x 3 calls)           |
| Total input tokens       | ~2,000 - 5,000             | ~8,000+                               |
| Total output tokens      | ~800 - 2,000               | ~4,000+                               |
| Latency                  | ~3 - 5s                    | ~6 - 10s                              |
| Cost per 1,000 requests  | ~$2.00 - $5.00             | ~$8 - $20                             |

Relative cost tier: Medium to High. This pattern runs at minimum 2x the cost of a
single LLM call. Poorly tuned thresholds can result in 3x or more iterations, tripling
the cost per request.

---

## Call Breakdown (per iteration)

| Call      | Purpose                                    | Est. input tokens | Est. output tokens |
|-----------|--------------------------------------------|-------------------|--------------------|
| Generate  | Produce candidate output                   | 300 - 800         | 200 - 600          |
| Evaluate  | Score output and provide feedback          | 400 - 1,200       | 50 - 200           |
| Optimize  | Convert feedback to improvement instruction| 200 - 500         | 50 - 150           |

Total per iteration (rough estimate): ~900 - 2,500 input tokens, ~300 - 950 output tokens.
At max_iterations=3, multiply these by 3. The generate call's input grows each iteration
if previous drafts and feedback are included in context.

---

## Latency Profile

Latency is additive across iterations, and each iteration is additive internally
(generate, then evaluate, then optimize are sequential).

P50 estimate (2 iterations): ~3 - 5s
P95 estimate (3 iterations): ~6 - 10s
Worst case (3 iterations + verbose generate outputs): ~10 - 15s

Unlike Parallel Calls, there is no structural opportunity to parallelize within this
pattern. All three calls per iteration are sequentially dependent.

---

## What Drives Cost Up

- Number of iterations. Each iteration adds approximately 3 LLM calls. Going from
  2 to 3 iterations adds ~50% more cost. A threshold set too high may always exhaust
  max_iterations.
- Context accumulation. If each generate call includes the full prior draft and all
  prior feedback, the input context doubles or triples each iteration. Avoid threading
  full history into the generate call.
- Verbose generate output. The evaluator reads the full generated output; long outputs
  mean expensive evaluation calls.
- Same model for generator and evaluator. If both use the most capable, expensive model,
  the total cost is roughly 2x per iteration.

---

## What Drives Latency Up

- Max iterations reached. If threshold is never met, the pattern always runs
  max_iterations times, each adding a full generate + evaluate cycle.
- Long output generation. Each generate call that produces 500+ tokens is meaningfully
  slower than one that produces 150 tokens.
- Evaluate call complexity. If the evaluator is asked to reason across many criteria,
  it produces longer chain-of-thought output before the SCORE/PASS lines.

---

## Cost Control Knobs

Lower the quality threshold. The threshold is the most powerful single control.
Dropping from 0.90 to 0.80 often reduces average iterations from 2.5 to 1.5,
cutting expected cost by ~40% with a modest quality impact.

Reduce the number of criteria. An evaluator given 8 criteria tends to find something
wrong every iteration. 2-3 concrete, measurable criteria converge faster.

Use a cheaper model for the evaluator. The evaluator's job is pattern-matching against
a rubric, not creative generation. A cheaper model often scores just as reliably for
structured criteria.

Pass only the improvement instruction to the generator, not the full prior draft.
The generator can produce a fresh response from the instruction without needing
the verbatim previous attempt.

Cap max_iterations at 2 by default. Most quality gains happen in iteration 1. Iteration 3
rarely improves on iteration 2 enough to justify the cost.

---

## Comparison to Related Patterns

| Pattern               | Est. LLM calls     | Est. cost tier    | Est. latency | Best when                                   |
|-----------------------|--------------------|-------------------|--------------|---------------------------------------------|
| Evaluator-Optimizer   | (2-3) x iterations | Medium to High    | High         | External evaluator + structured rubric      |
| Reflection            | (2-3) x iterations | Medium to High    | High         | Self-critique; no separate evaluator needed |
| Prompt Chaining       | N (fixed)          | Low               | Medium       | Quality acceptable in a single pass         |
