# Cost & Latency: Prompt Chaining

All figures are rough estimates based on a frontier-tier model (e.g., GPT-4o, Claude Sonnet)
at approximately $3/1M input tokens and $15/1M output tokens. Actual numbers vary significantly
by model, prompt length, and output verbosity.

---

## At a Glance

|                          | Typical (P50 estimate) | High end (P95 estimate) |
|--------------------------|------------------------|--------------------------|
| LLM calls per request    | 3                      | 5+ (with gate retries)   |
| Total input tokens       | ~800 - 2,000           | ~5,000+                  |
| Total output tokens      | ~300 - 900             | ~2,000+                  |
| Latency                  | ~1.5 - 3s              | ~5 - 8s                  |
| Cost per 1,000 requests  | ~$0.50 - $2.00         | ~$4 - $10                |

Relative cost tier: Low. Prompt Chaining is the cheapest multi-step pattern because the
number of LLM calls is fixed at design time and there are no dynamic loops.

---

## Call Breakdown

| Call     | Purpose                | Est. input tokens | Est. output tokens |
|----------|------------------------|-------------------|--------------------|
| Step 1   | Extract / classify     | 200 - 600         | 100 - 300          |
| Step 2   | Process / enrich       | 300 - 800         | 150 - 400          |
| Step 3   | Synthesize / format    | 400 - 1,000       | 100 - 300          |
| Gate     | Validate (if LLM-based)| 100 - 200         | 10 - 50            |

Note on token accumulation: each step feeds its output into the next step's input.
A 400-token output from step 2 adds 400 tokens to step 3's input. Unconstrained steps
cause token costs to compound across the chain.

---

## Latency Profile

Latency is strictly additive. Each step waits for the previous one to complete.
There is no opportunity for parallelism within a standard chain.

Rough per-step estimate:
- Step 1: ~300 - 600ms
- Step 2: ~400 - 700ms
- Step 3: ~300 - 500ms

P50 estimate for a 3-step chain: ~1.5 - 2.5s
P95 estimate: ~4 - 7s (caused by a verbose step 2 output inflating step 3 input,
or an occasional slow API response)

---

## What Drives Cost Up

- More steps. Each step is a full LLM call. A 5-step chain costs roughly 67% more than a 3-step chain.
- Output spillover. A verbose step N output becomes a large step N+1 input. Without output length constraints, costs compound across every step.
- Gate retries. If a gate rejects and the step re-runs, that is an extra LLM call plus an extra gate call.
- Long system prompts. A 500-token system prompt added to every call costs 500 x N_steps extra input tokens per request.

---

## What Drives Latency Up

- Number of steps. Latency equals the sum of all step latencies; there is no shortcut.
- Output length. Output tokens generate more slowly than input tokens are read; a step that writes 500 tokens takes meaningfully longer than one that writes 100.
- LLM-based gates. Each LLM gate adds a full round-trip (~200 - 400ms) per step.

---

## Cost Control Knobs

Add max_tokens to every LLM call and enforce a length constraint in the prompt
("Respond in under 150 words"). This is the highest-impact lever available.

Use a cheaper or smaller model for mechanical middle steps (extraction, formatting,
normalization) and reserve the more capable model for the final synthesis step.
A 10x cheaper model on steps 1 and 2 can cut total chain cost by 50-60%.

Replace LLM-based gates with code-based validation where possible. JSON schema
validation, regex checks, and length checks cost nothing. Reserve LLM gates for
cases that genuinely require semantic judgment.

Cache step 1 output when the same or similar input appears repeatedly. If step 1
is a classification or extraction step on stable content, the output is often identical
for semantically equivalent inputs.

Shorten the system prompt. Audit it periodically; context that was added "just in case"
accumulates quickly and is paid for on every call.

---

## Comparison to Related Patterns

| Pattern             | Est. LLM calls | Est. cost tier | Est. latency | Best when                        |
|---------------------|----------------|----------------|--------------|----------------------------------|
| Prompt Chaining     | N (fixed)      | Low            | Medium       | Steps are fixed at design time   |
| Parallel Calls      | N+1            | Medium         | Low          | Steps are independent            |
| Orchestrator-Worker | 2+N (dynamic)  | Medium         | Medium       | Steps are unknown at design time |
