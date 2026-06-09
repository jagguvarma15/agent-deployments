# Cost & Latency: Saga

All figures are rough estimates based on a frontier-tier model at approximately
$3/1M input tokens and $15/1M output tokens, plus typical DB / state-store overhead.
Saga's per-step overhead is small; compensation amplifies cost when it triggers.

---

## At a Glance

|                              | Typical (P50 estimate)              | High end (P95 estimate)             |
|------------------------------|--------------------------------------|--------------------------------------|
| Steps per saga               | 3 - 6                                | 8+                                   |
| LLM calls per saga (if used) | 1 per step (often 0 for pure tools) | 2-3 per step (LLM-driven steps)      |
| Total input tokens           | ~1,000 - 5,000                       | ~15,000+ (LLM-heavy sagas)           |
| Total output tokens          | ~100 - 1,000                         | ~3,000+                              |
| Saga-log writes              | 2-3 per step (`started` / `completed` + optional output) | 4+ per step on retry |
| End-to-end latency           | ~2 - 10s                             | ~30s+ (slow downstream + compensation) |
| Cost per 1,000 sagas (happy) | ~$1 - $10                            | ~$30 - $100                          |
| Cost per 1,000 sagas (compensated) | 1.5-2× the happy-path cost     | 3× (compensator does forward recovery) |

Relative cost tier: Medium (matches `metadata.json`). The pattern's own overhead — log
writes + the coordinator's decision flow — is small. Per-saga cost is dominated by the
underlying step work (LLM calls + tool calls); compensation roughly doubles spend
for the sagas that need it.

---

## Per-Saga Cost Breakdown

| Component                | Source                                          | Typical $ per 1k sagas (happy path) |
|--------------------------|--------------------------------------------------|--------------------------------------|
| LLM calls (per step, if used) | Input + output × model price                | $0.50 - $8                           |
| Tool calls (per step)    | Third-party APIs invoked by `do` functions      | $0 - $2                              |
| Saga log writes          | One INSERT per transition (start, done, etc.)   | < $0.01                              |
| Coordinator state checkpoint | LangGraph PostgresSaver or similar          | < $0.01                              |
| Compensation cost (when triggered) | `undo` functions × completed steps    | adds 0.5× to 1.5× of happy-path cost |

Backward recovery (release a lock, cancel a reservation) is usually cheap — same shape
as the `do`, sometimes lighter. Forward recovery (send a cancellation SMS, issue a
refund) is at least as expensive as the original `do` and may be more (a refund costs
the gross transaction fee plus the original processing fee).

---

## Latency Breakdown

Single saga, happy path, 4 steps:

| Stage                    | Typical | Notes                                                    |
|--------------------------|---------|----------------------------------------------------------|
| Coordinator boot         | 10-50ms | Load saga state from checkpoint, decide entry point      |
| Step.do (× N)            | 500ms - 3s each | LLM round-trip + tool call; varies wildly        |
| Saga-log writes (× 2N)   | 1-3ms each | One per started/completed                              |
| Final-state write        | 5-20ms  | Commit saga.run.done                                     |
| **Total** (4-step saga)  | ~2-10s  | Dominated by the steps themselves                        |

Compensation latency:

| Stage                    | Typical | Notes                                                    |
|--------------------------|---------|----------------------------------------------------------|
| Compensation walker boot | 10-30ms | Iterate completed_steps from the log                     |
| Step.undo (× N completed)| Often < step.do | Reversing a lock or cancelling a reservation is usually faster than acquiring/reserving |
| Saga-log writes (× 2N)   | 1-3ms each | One per compensation_started / compensation_done       |

A 4-step saga that fails at step 4 spends ~1.5-2× the happy-path latency: forward
through all 4 steps, then backward through the first 3 compensators.

---

## What Drives Cost Up

- **Step density.** A saga with 10 steps costs roughly 2.5× a saga with 4 steps,
  even at constant per-step cost — log writes, checkpoint overhead, and step
  serialization add up.
- **LLM-driven steps.** A step that's a pure tool call costs essentially nothing.
  A step that's an LLM-mediated decision costs the full LLM round-trip. Reserve
  LLM steps for places where decision logic genuinely needs reasoning; mechanical
  steps should be pure tool calls.
- **Compensation rate.** Every saga that compensates roughly doubles its cost (or
  more, with forward recovery). Drive the failing-step rate down via better retry
  and circuit-breaker handling at the underlying step (see
  `agent-deployments/docs/cross-cutting/resilience.md`).
- **Forward-recovery compensators.** Sending a cancellation SMS or issuing a refund
  costs real money. Where possible, **reorder the saga** so irreversible steps
  run last — then they never need compensation.
- **Retry storms on compensators.** A compensator that's retryable but the
  underlying downstream is down can re-spend its cost many times. Cap compensator
  retries at low N (3) and escalate to `partially_compensated` rather than
  retrying for hours.

---

## What Drives Latency Up

- **Slow downstream services.** Per-step latency dominates total saga time.
- **Long step lists.** Sequential serialization adds up; consider parallelizing
  independent steps (next section).
- **Compensation triggered late.** A 6-step saga that fails at step 6 walks back
  through 5 compensators — roughly doubling end-to-end latency.
- **Lease contention.** If multiple coordinators race for the same saga, the lease
  loser waits the full lease TTL before retrying. Tune `lease_ttl` to safely exceed
  the longest step.
- **Saga-log writes on a slow DB.** Per-step writes (×2) become noticeable if the
  saga has 10+ steps and the DB sits behind a slow connection pool. Use a local
  pool; consider batching transitions.

---

## Cost Control Knobs

**Reorder steps so irreversible operations run last.** A saga where SMS is step 1
needs forward-recovery if anything later fails. The same saga where SMS is step 4
never sends the SMS at all on early-step failures. Free cost reduction.

**Parallelize independent steps.** If two steps don't depend on each other's
outputs, run them in parallel (separate sub-graphs that join). Saves wall time
without changing total LLM cost. Both still log independently.

**Cheap models for mechanical steps.** Steps that compose a payload or pick a
candidate from a ranked list don't need Opus. See
`agent-deployments/docs/cross-cutting/model-routing.md` per-role table.

**Cap compensator retries low (3).** A failing compensator should escalate fast,
not retry for hours. Pay the human-attention cost rather than burning LLM dollars
into a permanent failure.

**Trim saga-log payloads.** The log's `payload_in` and `output` columns are for
compensator reference, not full request bodies. Store only what the `undo`
function actually needs (e.g., the reservation snapshot, not the entire response).

---

## Latency Control Knobs

**Bound per-step timeouts.** Without timeouts, one slow step pins the saga.
Pair every step with a per-call timeout (see resilience.md § Timeouts).

**Use a fast checkpoint backend.** LangGraph's PostgresSaver is reliable but its
write latency is the floor for inter-step latency. RedisSaver can be faster for
short sagas where durability requirements are looser.

**Idempotency on `do` lets you retry without restart.** Per-step retries are
cheaper than coordinator-restart-from-checkpoint because you skip the boot tax.

---

## Comparison to Related Patterns

| Pattern         | Est. LLM calls / invocation | Est. cost tier | Est. latency | Best when                                  |
|-----------------|-----------------------------|----------------|--------------|--------------------------------------------|
| Tool Use        | 2+ per round                | Low-Medium     | Low          | Single-shot tool dispatch                  |
| Prompt Chaining | 1 per step                  | Low            | Low-Medium   | Sequential steps that don't need rollback  |
| Saga            | 1 per step (often 0)        | Medium         | Medium-High  | Multi-step with compensation requirements  |
| Plan-and-Execute| 2-5 per task                | Medium-High    | Medium-High  | Dynamic plans with checkpoints (no rollback semantics) |

Saga's distinctive cost shape: the **conditional doubling** of cost when compensation
triggers. Routing or Tool Use have predictable per-invocation costs; saga has bimodal
cost (happy path vs compensation path), which is what drives the "drive down the
failing-step rate" guidance.
