# Saga — Implementation

Two structural approaches, both running the same rebooking flow.

1. **Orchestration with LangGraph** — a single state machine owns the step list, the log, and the compensation walker.
2. **Choreography on Redis Streams** — each step is an independent consumer reacting to step-completed / step-failed events.

The reference Python code in [`code/python/saga.py`](code/python/saga.py) implements the orchestration variant — start there. The choreography sketch below is illustrative.

---

## Orchestration with LangGraph

LangGraph is a natural fit for orchestration sagas because its state machine and persistence model align directly with the saga lifecycle.

### State

```python
from typing import TypedDict, Literal

class SagaState(TypedDict):
    saga_id: str
    payload: dict
    completed_steps: list[str]
    step_outputs: dict[str, dict]
    failed_step: str | None
    compensations_run: list[str]
    final_state: Literal["pending", "completed", "compensated", "partially_compensated"]
```

`completed_steps` is the list to walk in reverse on compensation. `step_outputs` is what the compensators read — never the live world, always the snapshot.

### Graph

Each step is a forward node with an edge to either the next step or the compensation node. Compensation is itself a node that loops, popping one step at a time off `completed_steps` and invoking its `undo`.

```python
from langgraph.graph import StateGraph, END

def step_node(step_id, do_fn, undo_fn):
    def runner(state: SagaState) -> SagaState:
        log.info("saga.step.start", saga_id=state["saga_id"], step_id=step_id)
        try:
            output = do_fn(state["payload"], state["step_outputs"])
        except RetryableError:
            raise   # LangGraph's retry policy handles re-entry
        except Exception as exc:
            log.error("saga.step.fail", saga_id=state["saga_id"], step_id=step_id,
                      error_class=type(exc).__name__)
            state["failed_step"] = step_id
            return state
        state["completed_steps"].append(step_id)
        state["step_outputs"][step_id] = output
        log.info("saga.step.done", saga_id=state["saga_id"], step_id=step_id)
        return state
    return runner

def compensate_node(undo_registry):
    def runner(state: SagaState) -> SagaState:
        while state["completed_steps"]:
            step_id = state["completed_steps"].pop()
            output = state["step_outputs"].get(step_id, {})
            try:
                undo_registry[step_id](state["payload"], output)
                state["compensations_run"].append(step_id)
                log.info("saga.compensation.done", step_id=step_id)
            except Exception as exc:
                log.error("saga.compensation.fail", step_id=step_id,
                          error_class=type(exc).__name__)
                state["final_state"] = "partially_compensated"
                return state
        state["final_state"] = "compensated"
        return state
    return runner

graph = StateGraph(SagaState)
graph.add_node("search",       step_node("search", do_search, undo_search))
graph.add_node("reserve",      step_node("reserve", do_reserve, undo_reserve))
graph.add_node("cancel_old",   step_node("cancel_old", do_cancel_old, undo_cancel_old))
graph.add_node("notify",       step_node("notify", do_notify, undo_notify))
graph.add_node("compensate",   compensate_node({
    "search": undo_search, "reserve": undo_reserve,
    "cancel_old": undo_cancel_old, "notify": undo_notify,
}))

def route_after(step: str):
    def router(state: SagaState) -> str:
        return "compensate" if state.get("failed_step") else next_step(step)
    return router

graph.add_conditional_edges("search",     route_after("search"))
graph.add_conditional_edges("reserve",    route_after("reserve"))
graph.add_conditional_edges("cancel_old", route_after("cancel_old"))
graph.add_conditional_edges("notify",     route_after("notify"))
graph.add_edge("compensate", END)
graph.set_entry_point("search")
saga = graph.compile(checkpointer=postgres_saver)
```

### Persistence

The `checkpointer` parameter is what makes the saga crash-resilient. LangGraph persists the full `SagaState` after every node returns. On restart, the coordinator loads the last checkpoint and resumes from there — either continuing forward or jumping into the compensation node, depending on `failed_step`.

For production, use `langgraph.checkpoint.postgres.PostgresSaver` or `RedisSaver`. The saga log table (from [design.md](./design.md)) sits alongside as the append-only audit trail.

### Wiring the rebooking flow

```python
def do_search(payload, outputs):
    return search_alternative_slots(
        restaurant_id=payload["restaurant_id"],
        time_window=payload["time_window"],
        party_size=payload["party_size"],
    )  # {search_id: str, candidates: [...]}

def undo_search(payload, output):
    release_search_lock(output["search_id"])

def do_reserve(payload, outputs):
    best = outputs["search"]["candidates"][0]
    return reserve_slot(slot_id=best["slot_id"])  # {reservation_id: str, snapshot: {...}}

def undo_reserve(payload, output):
    cancel_reservation(output["reservation_id"])

def do_cancel_old(payload, outputs):
    snapshot = capture_reservation(payload["original_reservation_id"])
    cancel_original(payload["original_reservation_id"])
    return {"snapshot": snapshot}

def undo_cancel_old(payload, output):
    recreate_reservation(output["snapshot"])

def do_notify(payload, outputs):
    return notify_customer(
        customer_id=payload["customer_id"],
        new_reservation_id=outputs["reserve"]["reservation_id"],
        idempotency_key=f"rebook:{payload['saga_id']}",
    )

def undo_notify(payload, output):
    # Forward recovery — the original SMS can't be unsent. Send a cancellation.
    notify_failed_rebook(
        customer_id=payload["customer_id"],
        idempotency_key=f"rebook:cancel:{payload['saga_id']}",
    )
```

Note the deliberate ordering: `notify` is **last** because the SMS is irreversible. If reservation steps fail, we never sent the SMS at all. If `notify` itself fails, we have to send a cancellation SMS (forward recovery) — which is more expensive UX than not sending.

---

## Choreography on Redis Streams

Choreography removes the central coordinator. Each step is its own consumer; steps publish step-completed events; downstream consumers react.

### Event shapes

```json
{ "event": "rebook.step.search.done",     "saga_id": "...", "output": {...} }
{ "event": "rebook.step.search.failed",   "saga_id": "...", "error_class": "...", "error_message": "..." }
{ "event": "rebook.step.reserve.done",    "saga_id": "...", "output": {...} }
{ "event": "rebook.compensate.requested", "saga_id": "...", "failed_step": "reserve" }
```

### Consumer pattern

Each step has two consumers:

- **Forward consumer** — subscribes to the previous step's `.done` event; runs its own `do`; publishes its own `.done` (or `.failed`).
- **Compensation consumer** — subscribes to `rebook.compensate.requested`; if its own step is in the saga log's `completed_steps`, runs its `undo`; publishes `rebook.compensation.{step_id}.done`.

```python
# search consumer (entry point — triggered by the rebook.requested event)
async def on_rebook_requested(saga_id: str, payload: dict):
    output = await search_alternative_slots(...)
    await xadd("rebook.events", {
        "event": "rebook.step.search.done", "saga_id": saga_id, "output": output,
    })

# reserve consumer — reacts to search.done
async def on_search_done(saga_id: str, payload: dict, prior_output: dict):
    try:
        output = await reserve_slot(prior_output["candidates"][0])
        await xadd("rebook.events", {
            "event": "rebook.step.reserve.done", "saga_id": saga_id, "output": output,
        })
    except PermanentError as exc:
        await xadd("rebook.events", {
            "event": "rebook.step.reserve.failed", "saga_id": saga_id,
            "error_class": type(exc).__name__, "error_message": str(exc),
        })
        await xadd("rebook.events", {
            "event": "rebook.compensate.requested", "saga_id": saga_id, "failed_step": "reserve",
        })

# search compensator — reacts to compensate.requested if it's in completed_steps
async def on_compensate_requested(saga_id: str, failed_step: str):
    log_state = await load_saga_log(saga_id)
    if "search" in log_state.completed_steps:
        await release_search_lock(log_state.outputs["search"]["search_id"])
        await xadd("rebook.events", {
            "event": "rebook.compensation.search.done", "saga_id": saga_id,
        })
```

### Tradeoffs

Choreography removes the single point of failure of the coordinator but **shifts the complexity into the log + the event schema**. You still need a durable saga log; you still need to know which steps completed; the difference is that everyone writes to the log, not just the coordinator.

Common gotcha: a new consumer is added without registering its compensator. Saga "succeeds" because no one notices the missing rollback. Mitigation: a saga manifest in version control that lists every step + every compensator; CI fails the build if a step exists without a paired compensator.

For the rebooking recipe, orchestration is the right starting point. Move to choreography only when team boundaries (one team per platform) make the single coordinator a deployment-coupling bottleneck.

---

## Testing

- **Happy-path test** — run the full saga; assert `final_state == "completed"` and each forward `do` called exactly once.
- **Compensation test** — inject a failure in step 3; assert compensators for steps 1 and 2 run in reverse order, and `final_state == "compensated"`.
- **Compensator-failure test** — inject a failure in `undo_reserve`; assert `final_state == "partially_compensated"` and the alert hook fires.
- **Idempotency test** — run the saga, kill the coordinator mid-flight, restart from checkpoint; assert each step still runs exactly once (no double-do, no double-undo).
- **Replay test** — load an old saga log; replay its events into a new coordinator; assert the same final state. This is what makes a stuck saga recoverable manually.

---

## Operational handles

- **Saga lease** — orchestration coordinators acquire a per-saga lease before running a step. Prevents two coordinators from racing on the same saga. See `agent-deployments/docs/cross-cutting/distributed-locking.md` for the lease pattern.
- **Saga-stuck alert** — any saga in `partially_compensated` state for > 5 minutes pages on-call. This is the most important saga alert.
- **Manual compensation tool** — an operator CLI that can re-run a specific compensator with audit logging. See `agent-deployments/docs/cross-cutting/audit-logging.md`.
- **Replay tool** — given a saga_id, dump its log; given a log + a fix, replay it. Treat compensators with the same care as DLQ replays.
