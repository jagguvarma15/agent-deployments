# Long-Horizon — Implementation

> Code variants under `code/python/` are not yet shipped; the pseudocode here is framework-agnostic and mirrors [`schemas/state.py`](schemas/state.py).

## Storage choice

Two stores, often colocated. Pick durability shape per workload:

| Store | Postgres | Redis (with AOF) | DynamoDB / equivalent |
|---|---|---|---|
| Checkpoint snapshot | ✓ (default) | ✓ for high write rate | ✓ for multi-region |
| Event log | ✓ (single table, append-only) | ✓ (streams) | ✓ |
| Transactional pairing | ✓ (same TX) | Lua script | Conditional writes |
| Best for | Most teams | High write-rate fleets | Multi-region failover |

The default for most teams is Postgres with both tables in the same database, and a single transaction wrapping every step's checkpoint + event-log append. That guarantees the two never diverge.

```sql
-- Tables (sketch)
CREATE TABLE long_horizon_checkpoints (
    task_id     TEXT PRIMARY KEY,
    version     BIGINT NOT NULL,
    state_blob  JSONB NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE long_horizon_events (
    task_id     TEXT NOT NULL,
    seq         BIGINT NOT NULL,
    kind        TEXT NOT NULL,
    payload     JSONB NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (task_id, seq)
);
CREATE INDEX ON long_horizon_events (task_id, seq);
```

## The tick loop

The tick is the unit of work. One tick advances the task by zero or more steps and persists the new state.

```python
def tick(task_id):
    with db.transaction() as tx:
        state = load_checkpoint(tx, task_id)
        events_since = load_events_since(tx, task_id, state.version)
        state = apply_events(state, events_since)

        if state.status in TERMINAL:
            return state

        if deadline_passed(state):
            state = mark_aborted(state, reason="deadline_exceeded")
            persist(tx, state, [event("aborted", reason="deadline")])
            return state

        next_step = state.plan.next_pending_step()
        if next_step is None:
            state = mark_completed(state)
            persist(tx, state, [event("completed")])
            return state

        # Execute the step. May call a sub-agent, tool, or LLM directly.
        result = execute(next_step, state)
        state = state.apply_step_result(next_step, result)
        events = [event("step_started", step_id=next_step.id),
                  event("step_completed", step_id=next_step.id, result=result)]
        persist(tx, state, events)
        return state
```

The transaction is critical: the checkpoint write + event-log appends commit together or roll back together. Without the transaction, a crash between them leaves the two stores inconsistent.

## Resume contract

Any worker can resume any task. The contract:

1. Workers read tasks from a queue ("tasks ready to tick") or a cron ("scan for tasks where `next_tick_at < now`").
2. A worker takes a per-task lock (DB row lock, Redis lock with TTL) before calling `tick()`. Without the lock, two workers on the same task is a write conflict.
3. `tick()` may take seconds (most steps) to many minutes (a sub-agent that takes its time). Lock TTL must exceed the step's max wall-clock.
4. On worker crash, the lock expires; another worker picks the task up. The transactional checkpoint guarantees no work is lost.

```python
def worker_iteration():
    task_id = queue.poll(timeout=10s)
    if task_id is None:
        return
    with task_lock(task_id, ttl=600) as lock:
        if not lock.acquired:
            return    # someone else has it
        state = tick(task_id)
        if state.status in TERMINAL:
            queue.ack(task_id)
        else:
            queue.requeue(task_id, delay=state.next_tick_delay())
```

## Re-planning

Plans get stale. The runner exposes an explicit `replan()` that the executor can request when a step result implies the world changed:

```python
def execute(step, state):
    result = step.executor(state.context_for(step))
    if result.signals_replan():
        new_plan = replan(state.goal, state.plan, state.completed_steps, result)
        state = state.replace_plan(new_plan)
        record_event("replanned", reason=result.replan_reason)
    return result
```

Re-planning is expensive (planner-class model call). Don't re-plan every step; re-plan when the executor explicitly asks. Common triggers: step returned "I can't do this with the current approach"; external state changed (a dependency removed); user updated the goal.

## Idempotency keys per step

Every step that has external side effects gets a stable idempotency key derived from `(task_id, step_id, attempt)`. The downstream system uses this key for deduplication.

```python
@dataclass
class StepInvocation:
    task_id: str
    step_id: str
    attempt: int                # increments on retry

    @property
    def idempotency_key(self) -> str:
        return f"lh:{self.task_id}:{self.step_id}:{self.attempt}"
```

When a step is retried (after a crash, before the worker confirmed completion), the new attempt uses a new key. Provider semantics differ: some dedupe on the same key (the retry is a no-op), some require the same key to confirm the in-flight call. Match the step's semantics to the provider.

## Context engineering inside the runner

The runner is responsible for assembling the input to each step. The default strategy:

```python
def context_for(state, step):
    return StepContext(
        goal=state.goal,
        plan_recap=state.plan.compact_recap(),         # current step + remaining steps
        completed_recap=state.completed.compact_recap(), # what we did, in 10 sentences
        relevant_artifacts=state.virtual_fs.list_for(step),
        upstream_results=state.results_relevant_to(step),
    )
```

The `compact_recap` is itself an LLM call (often Haiku-class) — but it's cached per state version. As long as the state hasn't advanced past a checkpoint, the recap is reused.

If you skip compaction, every resume eventually fails: the planner's context grows linearly with task age until it exceeds the window.

## Virtual filesystem

For tasks where sub-agents produce large artifacts (research notes, generated code, intermediate analyses), pass file paths, not file contents. The virtual filesystem is just a per-task directory in object storage with read/write tools the sub-agents have.

```
gs://my-tasks/onboard_acme_corp/
├── plan.json
├── notes/
│   ├── 2026-06-01-discovery.md
│   ├── 2026-06-02-provisioning.md
│   └── 2026-06-03-smoke-tests.md
├── artifacts/
│   ├── tenant_config.yaml
│   └── seed_data.csv
└── decisions/
    └── 2026-06-02-region-choice.md
```

The runner passes the directory listing to the planner; the sub-agents read what they need and write what they produced. The planner's context stays tiny.

## Pitfalls

- **No idempotency on a step with side effects.** Eventually a resume duplicates the side effect. Always design the idempotency strategy before deploying.
- **Reducer reads non-deterministic data.** A reducer that does `datetime.now()` or reads from a mutable store can't be replayed reproducibly. Capture the time and the data in the event payload.
- **No deadline.** A task with no overall deadline can stall indefinitely; the operator only finds out when a customer complains. Always set a deadline; surface deadline-elapsed in alerting.
- **Storing the entire transcript in the checkpoint.** Checkpoints become megabytes; loading them dominates the tick latency. Use the recap + virtual filesystem.
- **Re-planning every tick.** Burns money and produces plan thrash. Re-plan only on explicit triggers.
- **Tying `tick()` to a long-lived process.** Defeats the harness — a process restart loses the in-progress tick. `tick()` should be quick (a step or a few) and forward-only; long-running steps happen *inside* the executor, not inside the tick loop.
- **No stuck-task detector.** Tasks silently stall when an upstream dependency is down and no step is running. A separate stuck-task scanner is mandatory.

## Testing

- **Per-reducer unit test.** Each reducer function gets fixtures: `(state_before, event) → state_after`. Determinism is provable.
- **Resume replay test.** Given a captured checkpoint + event sequence, two replays produce identical state.
- **Idempotency contract test.** Each step that has side effects has a test that exercises it twice with the same idempotency key and asserts the side effect happened once.
- **Long-running integration test.** End-to-end test with a mock executor that injects crashes between steps; asserts the resume picks up where it left off.
- **Stuck-task detector test.** Synthetic task that stalls; the scanner detects it.

## What we deliberately don't ship

- A specific workflow engine. Temporal, Step Functions, Inngest, Airflow, custom — all viable hosts for this pattern. The pattern lives above the engine.
- A specific virtual filesystem provider. S3 / GCS / Azure Blob / NFS all work; the runner sees a directory abstraction.
- A specific recap model. Haiku-class works for most flows; a fine-tuned recap model can be plugged in.
