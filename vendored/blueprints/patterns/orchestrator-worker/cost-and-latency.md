# Cost & Latency: Orchestrator-Worker

All figures are rough estimates based on a frontier-tier model at approximately
$3/1M input tokens and $15/1M output tokens. This pattern has high variance because
the orchestrator decides at runtime how many workers to invoke.

---

## At a Glance

|                          | Typical (P50 estimate) | High end (P95 estimate)            |
|--------------------------|------------------------|------------------------------------|
| LLM calls per request    | ~4 - 6 (2+N workers)  | ~10+ if orchestrator over-decomposes|
| Total input tokens       | ~2,000 - 5,000         | ~10,000+                           |
| Total output tokens      | ~800 - 2,500           | ~5,000+                            |
| Latency                  | ~3 - 6s                | ~8 - 15s                           |
| Cost per 1,000 requests  | ~$2.00 - $6.00         | ~$12 - $30                         |

Relative cost tier: Medium to High. Unlike Prompt Chaining, the number of LLM calls
is not fixed. The orchestrator decides the work scope, so a poorly constrained
decomposition prompt can balloon costs unpredictably.

---

## Call Breakdown

| Call            | Purpose                               | Est. input tokens | Est. output tokens |
|-----------------|---------------------------------------|-------------------|--------------------|
| Decompose       | Plan sub-tasks and assign workers     | 300 - 800         | 150 - 400          |
| Worker 1 to N   | Execute each assigned sub-task        | 400 - 1,200 each  | 200 - 600 each     |
| Synthesize      | Combine all worker outputs            | 600 - 3,000+      | 300 - 800          |

Synthesis input grows with the total output of all workers. Three workers each producing
500 tokens of output creates a 1,500-token synthesis input before any prompt instructions.

---

## Latency Profile

Latency depends on whether workers run sequentially or in parallel.

Sequential workers (default): latency = decompose + sum(worker latencies) + synthesize
Parallel workers: latency = decompose + max(worker latencies) + synthesize

P50 estimate (3 sequential workers): ~3 - 6s
P95 estimate (5+ workers or sequential with slow workers): ~8 - 15s

If workers run in parallel (requires thread pool or async implementation), P50 drops
to roughly: decompose (~500ms) + max(worker latencies) (~1.5s) + synthesize (~800ms) = ~3s.

---

## What Drives Cost Up

- Number of workers. The orchestrator decides this at runtime. Without a cap in the prompt
  or in code, a complex task can generate 8-10 workers on a single request.
- Worker verbosity. Workers that return long outputs inflate synthesis input tokens.
  Synthesis often uses the most capable model, so this is expensive.
- Decomposition retries. If the JSON parse fails and the orchestrator is retried, you pay
  for an extra decompose call before any workers run.
- System prompt duplication. If each worker call includes the full task context and system
  prompt, and there are 6 workers, that context is paid for 6 times.

---

## What Drives Latency Up

- Number of workers running sequentially. Each worker adds its full latency to the total.
- Synthesis input size. A large synthesis context (many verbose workers) makes the final
  call slow and expensive.
- Orchestrator indecision. If the orchestrator is unsure about decomposition and produces
  ambiguous sub-tasks, workers may run partially or fail, triggering re-orchestration.

---

## Cost Control Knobs

Cap sub-task count in the decomposition prompt and in code. Add an instruction like
"Produce no more than 4 sub-tasks" and enforce it with a hard cap before dispatching workers.
This is the single highest-impact control for this pattern.

Constrain worker output length. Add a length instruction to each worker's system prompt:
"Respond in under 250 words." Each 100 tokens of worker output reduction saves 100 tokens
on synthesis input, multiplied by worker count.

Run workers in parallel where sub-tasks are independent. Parallelism does not reduce token
cost, but it cuts wall-clock latency significantly, often from 6-10s to 2-4s.

Use cheaper models for routine workers. Workers doing summarization, extraction, or
formatting can often use a faster, cheaper model. Reserve the most capable model for
the orchestrator and synthesizer, which require complex reasoning.

Separate the decompose call from the worker system prompts. Pass only the specific
sub-task to each worker, not the full original task and all prior context.

---

## Comparison to Related Patterns

| Pattern             | Est. LLM calls  | Est. cost tier     | Est. latency | Best when                               |
|---------------------|-----------------|--------------------|--------------|-----------------------------------------|
| Orchestrator-Worker | 2+N (dynamic)   | Medium to High     | Medium       | Task scope unknown at design time       |
| Prompt Chaining     | N (fixed)       | Low                | Medium       | Task scope fixed, steps sequential      |
| Parallel Calls      | N+1 (fixed)     | Medium             | Low          | Fixed branches, independent outputs     |
| Plan & Execute      | 1+N (fixed plan)| Medium             | Medium       | Task needs ordered, trackable steps     |
