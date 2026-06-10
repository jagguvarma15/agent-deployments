# Cost & Latency: Long-Horizon

The pattern's cost shape is unusual: cost accumulates over **task lifetime**, not per call. A task may live for two weeks while idle most of that time, paying only storage. When it does work, it pays per-tick LLM costs plus per-step executor (sub-agent) costs. Latency is decoupled from compute — wall-clock is dominated by waits, not work.

---

## At a Glance

|                                  | Typical (P50)                       | High end (P95)                      |
|----------------------------------|-------------------------------------|-------------------------------------|
| Task wall-clock                  | Hours to days                       | Weeks                               |
| Compute cost per active step     | $0.01–$0.50 (sub-agent dependent)   | $5                                  |
| Storage cost per task per day    | < $0.001 (checkpoint + log)         | < $0.01 (large artifacts on virt FS)|
| Tick latency                     | 100ms – 10s                         | 60s                                 |
| Resume overhead                  | 50–300ms (checkpoint load + replay) | 1s                                  |
| Replan cost                      | $0.05–$0.30 (planner model call)    | $1                                  |

Relative cost tier: Medium-High over task lifetime, dominated by sub-agent step costs. Latency tier: very-high in wall-clock; per-tick latency is low.

---

## Per-task Cost Breakdown

Cost accumulates across the task lifetime. Most of it is in the steps; the harness is cheap.

| Component | Per-task cost | Notes |
|---|---|---|
| Initial plan | $0.05–$0.30 (Opus / Sonnet planner) | One call at kickoff |
| Per-step recap (compact) | $0.001 per step (Haiku) | Generated before each sub-agent invocation |
| Per-step executor (sub-agent) | $0.01–$0.50 per step | Dominant cost; depends on sub-agent role + model |
| Re-plan calls | $0.05–$0.30 per re-plan | Average 0–2 per task |
| Storage (checkpoint + event log) | < $0.001 per day | Linear in days × event volume |
| Virtual filesystem storage | $0.0001–$0.01 per day | Depends on artifact size |
| Audit / observability emission | < $0.0001 per tick | Trace + log infrastructure |

**Concrete:** A 12-step onboarding task with Sonnet sub-agents averaging $0.10 per step, an Opus planner, two re-plans, and 14 days in flight: ~$1.85 in LLM cost + ~$0.05 in storage. The same task done by one Opus agent in a request: ~$5–$10 (Opus reads the full transcript every step) — and it can't survive a 14-day wait.

---

## Latency Breakdown

Wall-clock per task is dominated by waits the agent didn't choose:

| Source | Typical |
|---|---|
| External dependency wait (data provider, webhook, human signal) | Hours to days |
| Sub-agent step execution | Seconds to minutes |
| Tick scheduling (queue / cron latency) | Seconds to minutes |
| Checkpoint load + replay | 50–300ms per resume |
| Per-step LLM latency | 2–30s per step |

For an onboarding task with a 24h "wait for data provider" step and 11 other steps averaging 5 minutes each: ~25 hours wall-clock; ~1 hour of actual compute time. The pattern is doing what it should — the harness lets the agent stop holding resources during the wait.

---

## What Drives Cost Up

- **Over-spawning sub-agents.** Every step doesn't need a sub-agent. Steps that are one tool call should call the tool directly.
- **Re-plan thrash.** Each re-plan is a planner call. If re-plans average > 2 per task, the executor is too eager to invalidate the plan.
- **Bloated recaps.** If the recap call is expensive (full Opus on a long transcript), it dominates. Use Haiku for recaps; cap recap length aggressively.
- **Storing full transcripts in the checkpoint.** Larger checkpoints mean larger reads on every resume. Move artifacts to the virtual filesystem.
- **Auto-retry on every step failure.** Step failures should sometimes abort; retrying expensive sub-agent invocations gets pricey.
- **Long deadlines + idle tasks.** Tasks that genuinely span weeks pay storage daily. If many tasks idle indefinitely, archival policy matters.

---

## What Drives Wall-Clock Up

- **External waits.** The dominant factor. The harness lets the wait happen; it doesn't shorten it. To shorten, redesign the workflow (parallelize independent waits, push the wait to a human-side queue with SLAs).
- **Queue scheduling lag.** If the worker queue runs every 5 minutes and the next tick is "now", the task waits up to 5 minutes per tick. For tasks with many quick ticks, that adds up. Use event-driven triggers (webhook → immediate tick) instead of pure cron.
- **Sub-agent latency.** A slow sub-agent step is a slow tick. The same per-role-model-selection lever as in [Sub-agents](../../primitives/sub_agents/overview.md) applies.
- **Resume overhead amortization.** If every tick does very little work, resume overhead dominates. Batch tick work where possible (one tick = several quick steps).

---

## Cost & Latency Control Knobs

**Right-size the recap.** Haiku-class recap, capped at ~500 tokens of summary. Don't pass the recap through Opus.

**Per-role models for sub-agents.** Standard sub-agent lever. Opus planner, Sonnet workers, Haiku for formatters / distillers.

**Cap re-plans per task.** Soft cap at 3 with an alert; hard cap at 5. Beyond that the agent is plan-thrashing and should escalate.

**Virtual filesystem instead of inline state.** Cuts checkpoint size 10–100×; resume latency drops proportionally.

**Archive completed tasks aggressively.** Keep the full event log for 30 days for audit; move older logs to cold storage. Checkpoint store should be lean.

**Use event-driven triggers for time-sensitive workflows.** If a webhook completes a step, that webhook directly enqueues the next tick — don't wait for cron.

**Cache the plan's compact recap.** The recap is a pure function of the state version. Cache it; reuse across ticks until the state advances.

**Per-task-class deadlines.** A 30-day deadline for an onboarding task is fine; a 30-day deadline for a "respond to support email" task is not. Tighten per-class.

**Stuck-task escalation policy.** Tasks that haven't progressed in 2× their expected step window get auto-escalated to human review. Don't pay storage and audit cost on dead tasks forever.

---

## Comparison to Related Patterns

| Pattern | Est. wall-clock | Est. LLM cost / task | Best when |
|---|---|---|---|
| Single-request agent (ReAct) | Seconds-minutes | $0.01–$0.10 | Work fits in one request |
| Saga | Minutes-hours | $0.05–$0.50 | Multi-step with compensation, completes in one process |
| Plan & Execute | Minutes-hours | $0.10–$1.00 | Multi-step with a plan, completes in one process |
| Long-Horizon | Hours-weeks | $0.50–$5.00+ (lifetime) | Spans process lifetimes; external waits dominate |
| Multi-Agent (single request) | Minutes | $0.20–$2.00 | Many sub-tasks in parallel within one request |

The distinctive cost shape: **storage cost is the floor, not the ceiling**. A task that idles for 13 days waiting on a webhook pays pennies. A task that does heavy work for one day pays dollars. Budget by task class, not by call.
