# Observability: Event-Driven

What to instrument, what to log, and how to diagnose failures in event-driven agents.

---

## Key Metrics

| Metric | Description | Alert if |
|--------|-------------|----------|
| `event_driven.consumer.lag` | Events behind on the stream (depth − last-consumed-id) | > 1,000 OR growing > 10/s for > 5 min |
| `event_driven.handler.duration_ms` | Per-handler processing latency (P50 / P95 / P99) | P95 > target SLO (typical 5s); P99 > 10s |
| `event_driven.handler.error_rate` | Errors / total handler invocations | > 1% over 5 min |
| `event_driven.poison.rate` | Events failing after `MAX_RETRIES` / total events | > 0.1% over 1 hour |
| `event_driven.dlq.depth` | Current dead-letter queue size | > 100 (notify); > 1,000 (page) |
| `event_driven.dlq.growth` | DLQ entries added per minute | > 10/min (notify); > 100/min (page) |
| `event_driven.idempotency.hit_rate` | Dedupe hits / total events | Sudden change (>20% delta); high values are informational, not alarming |
| `event_driven.handler.in_flight` | Concurrent handlers per consumer | Approaching the semaphore cap (>80% of bulkhead limit) |
| `event_driven.event_type.rate` | Events per second per `event_type` | Drop to 0 may mean producer broke; spike may need scaling |

Page on velocity + novelty (lag growing, DLQ surfacing a new `failure_reason`); notify on absolute thresholds. See `agent-deployments/docs/cross-cutting/dlq-operations.md` for tiered DLQ alert policy.

---

## Trace Structure

Each event becomes a **root span** — the consumer is not a long-lived request; each `xreadgroup` batch produces N independent root spans, one per event.

```mermaid
sequenceDiagram
    participant Broker as Event Source<br/>(Redis Stream / Kafka)
    participant Consumer
    participant Idem as Idempotency Store
    participant Agent
    participant Tools
    participant DLQ

    Broker->>Consumer: event {event_id, payload}
    activate Consumer
    note over Consumer: span = event_driven.handle<br/>event_id, handler_name, retry_count

    Consumer->>Idem: SETNX idemp:{event_id}
    Idem-->>Consumer: claimed | already_done

    alt already processed
        Consumer->>Broker: XACK
        note over Consumer: span ends — dedupe path
    else first time
        Consumer->>Agent: run(payload)
        activate Agent
        Agent->>Tools: tool calls
        Tools-->>Agent: results
        Agent-->>Consumer: outcome
        deactivate Agent

        alt success
            Consumer->>Idem: mark completed
            Consumer->>Broker: XACK
        else retryable
            note over Consumer: do not ACK; redelivery follows
        else permanent
            Consumer->>DLQ: XADD failure envelope
            Consumer->>Broker: XACK
        end
    end
    deactivate Consumer
```

---

## Span Reference

| Span name | Emitted | Key attributes |
|-----------|---------|----------------|
| `event_driven.handle` | Once per event (root span) | `event_id`, `event_type`, `idempotency_key`, `handler_name`, `handler_version`, `retry_count`, `partition_key`, `tenant_id`, `duration_ms`, `outcome` (ack/redeliver/dlq) |
| `event_driven.idempotency_check` | Once per event | `key`, `result` (claimed / already_done / claim_held_by_other), `duration_ms` |
| `event_driven.agent.run` | Once per event after idempotency claim | (delegates to nested tool / LLM spans from the underlying agent pattern) |
| `event_driven.persist_outcome` | After agent succeeds | `outcome_id`, `duration_ms` |
| `event_driven.ack` | Once per event on success | `stream`, `consumer_group`, `event_id` |
| `event_driven.dlq` | On permanent failure | `event_id`, `failure_reason`, `last_error_class`, `retry_count` |

Propagate `event_id` and `idempotency_key` through every child span so a stuck event can be queried end-to-end in the trace backend (`event_id = X` returns the consumer, idempotency check, agent run, every tool call, every retry).

---

## What to Log

### On successful handle

```
INFO  event_driven.handle.start    event_id=evt_01HVY...  event_type=reservation.cancelled  retry_count=0
INFO  event_driven.idempotency     event_id=evt_01HVY...  result=claimed
INFO  event_driven.agent.done      event_id=evt_01HVY...  outcome=rebooked  duration_ms=2840
INFO  event_driven.handle.done     event_id=evt_01HVY...  outcome=ack  duration_ms=2912
```

### On retry (non-ACK path)

```
WARN  event_driven.handle.retry    event_id=evt_01HVY...  retry_count=1  error_class=ReservationPlatformTimeout  next_attempt_in_s=15
```

### On DLQ routing

```
ERROR event_driven.handle.dlq      event_id=evt_01HVY...  retry_count=3  failure_reason=validation_failed
        last_error_class=ReservationPlatformError  dlq_id=dlq_01HVZ...
```

### On poison message (deserialization fail)

```
ERROR event_driven.handle.poison   event_id=evt_01HVY...  failure_reason=poison_message
        error="json.JSONDecodeError: Expecting value at line 1 col 0"  routed_to=dlq
```

### On idempotency dedup

```
INFO  event_driven.handle.dedupe   event_id=evt_01HVY...  reason=already_completed
```

---

## Common Failure Signatures

### Consumer lag climbing while ingress is flat

- **Symptom**: `consumer.lag` rising monotonically; producer-side throughput unchanged; handlers are slow.
- **Log pattern**: `handler.duration_ms` P95 is up 3–5× from the rolling mean.
- **Diagnosis**: A downstream dependency slowed (third-party API, DB, LLM). The handler is waiting on something external.
- **Fix**: Add a per-call timeout if you don't have one. Check the downstream's metrics directly. Add a circuit breaker per dependency (see `agent-deployments/docs/cross-cutting/resilience.md` § Circuit breakers) so a slow downstream fails fast instead of pinning workers.

### DLQ growing with a new `failure_reason`

- **Symptom**: `dlq.depth` ticking up; alert fires for `unknown error_class never seen before`.
- **Log pattern**: DLQ envelopes share a `last_error_class` that didn't exist in prior runs.
- **Diagnosis**: A recent deploy introduced a code path that throws an uncaught exception, OR a downstream changed its response shape and the consumer's parser broke, OR a new event_type appeared that the consumer doesn't know how to handle.
- **Fix**: `git log` for the recent deploy. Inspect a few DLQ entries via the DLQ replay CLI (see `agent-deployments/docs/cross-cutting/dlq-operations.md` § Replay CLI). Either roll back, patch + redeploy, then replay; or add the new failure mode to the consumer's handled-exceptions list.

### Idempotency hit rate spikes

- **Symptom**: `idempotency.hit_rate` jumps from steady-state ~1% to 20%+.
- **Log pattern**: `event_driven.handle.dedupe` lines flood the log.
- **Diagnosis**: Either the producer is double-publishing (broken upstream), or the consumer just restarted and is reprocessing in-flight events whose `XACK` was lost. The latter is normal and self-resolves; the former is a bug.
- **Fix**: Check the producer's emit rate and dedupe-key generation. If the producer is fine, the consumer is catching up — give it 5 min and watch the rate fall. If it stays high, look for an at-least-once → at-most-once misconfig at the producer.

### Handler in-flight count hitting the cap

- **Symptom**: `handler.in_flight` is consistently at or near the semaphore limit; `consumer.lag` rising.
- **Log pattern**: New events arrive faster than handlers complete; no errors, just slow.
- **Diagnosis**: Concurrency budget too small for the current ingress, OR handlers genuinely slowed and need a bigger budget temporarily.
- **Fix**: Scale consumer pods (horizontal) or raise the semaphore limit (vertical, with care — more in-flight means more memory). If you're already at max, the upstream needs throttling — see `agent-deployments/docs/cross-cutting/backpressure.md` for shed/cap strategies.

### Events stuck pending after a consumer crash

- **Symptom**: `XPENDING` shows events idle for > N minutes; total `consumer.lag` looks fine but specific events are stuck.
- **Log pattern**: An older consumer process disappeared; `XCLAIM` reaper isn't running or has wrong idle threshold.
- **Diagnosis**: Consumer crashed mid-handler. The broker holds the event in the "pending entries list" until another consumer `XCLAIM`s it.
- **Fix**: Run an `XCLAIM` reaper periodically (every 30s) that claims pending entries idle > `idle_ms`. Make sure the reaper logs how many it claimed; if the count stays nonzero across runs you may have a poison message that crashes every consumer it hits — those go to DLQ on max retries.
