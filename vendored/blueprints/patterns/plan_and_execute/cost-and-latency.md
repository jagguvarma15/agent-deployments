# Cost & Latency: Plan & Execute

All figures are rough estimates based on a frontier-tier model at approximately
$3/1M input tokens and $15/1M output tokens. Cost is more predictable than ReAct
because the plan is fixed upfront, but replanning events add significant overhead.

---

## At a Glance

|                          | Typical (P50 estimate)         | High end (P95 estimate)           |
|--------------------------|--------------------------------|-----------------------------------|
| LLM calls per request    | ~5 - 7 (plan + 4 exec steps)  | ~12+ (plan + steps + 1-2 replans) |
| Total input tokens       | ~3,000 - 7,000                 | ~12,000+                          |
| Total output tokens      | ~800 - 2,500                   | ~4,000+                           |
| Latency                  | ~4 - 8s                        | ~10 - 20s                         |
| Cost per 1,000 requests  | ~$2.50 - $6.00                 | ~$10 - $25                        |

Relative cost tier: Medium. Cheaper than ReAct for equivalent-complexity tasks because
context doesn't accumulate the same way. However, replanning events (when a step fails)
can double the cost of an affected request.

---

## Call Breakdown

| Call               | Purpose                            | Est. input tokens | Est. output tokens |
|--------------------|------------------------------------|-------------------|--------------------|
| Plan               | Generate full ordered plan         | 300 - 700         | 200 - 500          |
| Execute step 1-N   | Run each plan step                 | 400 - 1,000 each  | 150 - 400 each     |
| Replan (if needed) | Revise remaining steps on failure  | 500 - 1,200       | 200 - 500          |
| Tool call          | External action (not LLM)          | N/A               | N/A                |

Unlike ReAct, each execution call receives only the current step + a summary of prior
step outputs, not the full raw history. This keeps per-step input tokens more stable.

---

## Latency Profile

Latency is the sum of plan call + all sequential execution step calls.

Plan call estimate: ~500 - 1,000ms
Per execution step estimate: ~400 - 800ms (LLM) + tool latency
Replan call estimate: ~500 - 1,000ms (if triggered)

P50 estimate (4 execution steps, no replan): ~3 - 6s
P95 estimate (6 steps + 1 replan): ~8 - 15s

Steps are executed sequentially by default. If some steps are independent and you
implement parallel execution, P50 latency can drop significantly.

---

## What Drives Cost Up

- Number of plan steps. The primary cost driver, set at planning time. A plan with
  6 steps costs roughly 50% more than one with 4 steps on the same task.
- Replanning. A replan adds 1 extra LLM call plus re-execution of revised steps.
  A task that replans once typically costs 30-50% more than a task that does not.
- Step context size. Each execution step receives the outputs of prior steps as context.
  If step 2 produces a 600-token output and step 3 receives it as context, that 600
  tokens is paid for again in step 3's input.
- Planner verbosity. A planning call that returns a highly detailed plan (descriptions,
  notes, sub-steps per step) is more expensive to generate and harder to parse.

---

## What Drives Latency Up

- Step count (sequential execution)
- Tool latency within execution steps
- Replan events (add a full extra call before re-execution resumes)
- Complex synthesis or reasoning within individual steps

---

## Cost Control Knobs

Cap plan length in the planning prompt. Add "Produce 3 to 5 high-level steps" to
the planner prompt. Fewer, broader steps cost less and are less brittle than many
fine-grained steps.

Limit replan attempts. Set max_replan_attempts=1 or 2. Unlimited replanning on a
fundamentally broken plan wastes tokens on a task that will not succeed.

Pass only the immediately relevant prior context to each execution step, not all
prior step outputs. If step 5 only depends on step 3's output, pass step 3's output
rather than the accumulated outputs of steps 1 through 4.

Parallelize independent steps. If steps 2 and 3 are independent (the plan says so),
run them concurrently. This does not reduce token cost but halves the latency
contribution of those two steps.

Use a cheaper model for mechanical execution steps. The planner and replanner require
strong reasoning; execution steps that follow precise instructions often do not.

---

## Comparison to Related Patterns

| Pattern             | Est. LLM calls  | Est. cost tier | Est. latency | Best when                                 |
|---------------------|-----------------|----------------|--------------|-------------------------------------------|
| Plan & Execute      | 1+N (plan sets N)| Medium        | Medium       | Complex tasks, progress tracking needed   |
| ReAct               | 3-10+ (dynamic) | Medium, high var| Variable    | Steps unknown, adaptive tool use          |
| Orchestrator-Worker | 2+N (dynamic)   | Medium to High | Medium       | Parallel specialist delegation            |
