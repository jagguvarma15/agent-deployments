# Evolution: Saga + Event-Driven → Long-Horizon

This document traces how the [Long-Horizon pattern](./overview.md) emerges from [Saga](../saga/overview.md) and [Event-Driven](../event_driven/overview.md) when the work outgrows compensation alone and the wall-clock outgrows a process lifetime.

## The starting point: Saga inside a request

A team builds a saga to handle tenant onboarding. Step 1: provision DBs. Step 2: seed reference data. Step 3: smoke tests. Step 4: notify owner. Each forward step has a compensator. The saga runs inside one orchestrator process and completes in ~10 minutes for the happy path.

```mermaid
graph LR
    Req([Request]) --> Saga[Saga orchestrator process]
    Saga --> S1[Step 1]
    S1 --> S2[Step 2]
    S2 --> S3[Step 3]
    S3 --> S4[Step 4]
    S4 --> Done([Done])

    style Req fill:#e3f2fd
    style Saga fill:#fff3e0
    style Done fill:#e8f5e9
```

The pattern works until the team scales the use case.

## The breaking point

Sagas-in-a-request break down when:

- **Wall-clock grows past process lifetime.** Step 2 now waits for a third-party data provider whose SLA is 24 hours. The orchestrator process can't stay open that long; deploys, OOM kills, and routine restarts truncate the work.
- **External signals arrive days later.** Step 3 was reframed to "wait for the customer to confirm the smoke test results." That confirmation may arrive tomorrow, next week, or never.
- **Multiple resumption sources.** A webhook completes step 2; a cron resumes step 3 at midnight UTC; a human resolves step 4 from a UI. The saga doesn't have a vocabulary for "any of these advances the task."
- **The plan needs to change mid-task.** Halfway through onboarding, the customer requests a different DB region. The saga has no re-planning concept — it's a fixed forward + reverse list.
- **Compensation isn't what we want.** When step 3 fails after a week, "compensate the prior steps" means re-issuing API calls to data providers who charge per call. We want to *fix forward* — re-plan and continue — not unwind.
- **Resume isn't free.** Without a planned resume protocol, every restart causes either lost work or duplicate work.

## What changes

| Aspect | Saga-in-a-request | Long-horizon |
|---|---|---|
| Wall-clock | Minutes to hours | Hours to weeks |
| Process model | One orchestrator process | Many short-lived worker processes |
| State persistence | Saga log (for resume on crash) | Checkpoint snapshot + event log |
| Failure semantics | Compensate (undo) | Resume (continue) — compensation is a sub-flow |
| External signals | Synchronous (request/response) | Asynchronous (events arrive across days) |
| Plan model | Fixed list of `(do, undo)` pairs | Mutable plan; re-plan when world changes |
| Step executor | Inline code | Sub-agent invocation (typical) |
| Worker | One per saga | Many; any worker can pick up any task |

## The evolution, step by step

### Step 1: Persist state outside the process

The saga log goes from "for crash resume" to "the canonical source of truth." Every step writes a checkpoint before exiting. The orchestrator process is now stateless across steps — if it dies, another process picks up from the last checkpoint.

```
BEFORE:
  saga = Saga(steps=[...])
  result = saga.run()   # held in memory for minutes

AFTER:
  runner = LongHorizonRunner(task_id=tid, checkpoint_store=postgres, ...)
  runner.start(...)     # writes the first checkpoint
  # Process exits.
  # Later, possibly elsewhere:
  runner = LongHorizonRunner.resume(task_id=tid, ...)
  runner.tick()
```

### Step 2: Separate the snapshot from the event log

Pure snapshots lose audit detail. Pure event logs require full replay from t=0. The two-tier shape (snapshot every step, event log for everything in between) keeps storage and read costs bounded while preserving the full audit trail.

### Step 3: Move from "compensate" to "continue"

A saga's mental model is forward + reverse. A long-horizon agent's mental model is forward + replan. Compensation still happens — but for sub-flows that genuinely need to unwind (the saga pattern composes inside the long-horizon harness), not as the default failure mode.

### Step 4: Tickify the loop

Replace the long-lived `run()` with `tick()`. A tick advances the task by one or a few steps and returns. A queue worker, a cron, or an event handler all call `tick()`. The runner has no thread, no event loop, no held resources between ticks.

### Step 5: Make steps idempotent

Resume reissues work the previous worker may have partly done. Every step's side effects get an idempotency key derived from `(task_id, step_id, attempt)`. The downstream system deduplicates.

### Step 6: Add re-planning

The plan is no longer fixed. The runner exposes `replan()`; the executor asks for it when a step result implies the world changed enough. Without re-planning, long-running tasks ossify against stale assumptions.

### Step 7: Delegate steps to sub-agents

Each step becomes a [sub-agent](../../primitives/sub_agents/overview.md) invocation. The sub-agent has its own scoped context and tools. The runner's planner stays small (one tick = one planner call + one sub-agent spawn).

### Step 8: Add the virtual filesystem

Sub-agents produce large artifacts. Pass file paths, not file contents. The virtual filesystem becomes the long-horizon agent's "memory of what's been produced." This is the deep-agents shape.

### Step 9: Compose

Once long-horizon is in place, it composes:

- **+ [Saga](../saga/overview.md)** — sub-flows that need compensation use saga semantics for those step ranges.
- **+ [Event-Driven](../event_driven/overview.md)** — external signals (webhooks arriving days later) flow through the event queue and trigger ticks.
- **+ [Multi-Agent](../multi_agent/overview.md)** — the long-horizon runner IS the supervisor. Multi-Agent is the topology; long-horizon is what makes it durable across time.
- **+ [Human in the Loop](../../modifiers/human_in_the_loop/overview.md)** — `requires_human` termination resolves through HITL; once decided, a HITL webhook calls `tick()`.

## When to make this transition

**Stay with Saga-in-a-request when:**

- Total wall-clock is comfortably within a process lifetime (< 30 min typical).
- No external signals arrive after the request.
- Compensation IS the right failure mode for all steps.
- The plan is genuinely fixed.

**Evolve to Long-Horizon when:**

- Wall-clock spans process lifetime (deploys, restarts).
- External signals arrive on independent timelines (webhooks, cron, human signals).
- Steps want to re-plan, not unwind.
- The task is composed of sub-agent invocations.
- You want to operate the task with cron / queue workers, not long-running orchestrator processes.

## What you gain and lose

**Gain:** Tasks that span weeks; resume after any crash; multiple resumption sources; explicit re-planning; sub-agent delegation per step; the deep-agents shape; observability per task lifetime; operability (cron / queue workers replace long-lived orchestrators).

**Lose:** Storage cost over task lifetime; the operational discipline of idempotency-per-step; the harness work to build (or buy) checkpoint + event-log + tick worker; the difficulty of eval and regression for tasks no two of which run the same way.

## Evolves into

When long-horizon itself grows:

- **Persistent autonomous agents** — the runner becomes always-on; tasks don't end, they evolve. The harness adds explicit goal lifecycle (active → paused → archived). The agent is a persistent identity, not a single task.
- **Cross-task knowledge transfer** — successful task patterns get distilled into reusable plan templates; the planner consults a library. The pattern starts looking like [Skills](../../primitives/skills/overview.md) at the plan level.
- **Workflow-engine integration** — Temporal / Step Functions / Inngest take over the harness; the pattern moves into "what to put inside the workflow," not "how to build the workflow." Pick this when your team's operational ceiling matters more than the pattern's portability.
