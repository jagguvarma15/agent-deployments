# Cost & Latency: Event-Driven

All figures are rough estimates based on a frontier-tier model at approximately
$3/1M input tokens and $15/1M output tokens, plus typical broker + state-store overheads.
Event-driven adds a small per-event tax (broker dequeue + idempotency check + ACK) on top
of whatever underlying agent pattern the handler implements (Tool Use, ReAct, RAG, etc.).

---

## At a Glance

|                              | Typical (P50 estimate)         | High end (P95 estimate)               |
|------------------------------|--------------------------------|---------------------------------------|
| LLM calls per event          | 1 - 3 (depends on handler)     | 5+ (multi-turn ReAct handler)         |
| Total input tokens           | ~800 - 4,000                   | ~10,000+                              |
| Total output tokens          | ~100 - 800                     | ~2,000+                               |
| Broker overhead per event    | 1 - 5ms                        | 20ms (broker under load)              |
| Idempotency check            | 1 - 3ms (Redis SETNX + GET)    | 10ms (Redis tail latency)             |
| End-to-end latency           | ~1 - 5s                        | ~10s (slow downstream + retries)      |
| Cost per 1,000 events        | ~$0.50 - $5                    | ~$10 - $30                            |

Relative cost tier: Medium (matches `metadata.json` declared value). The pattern itself
adds little cost; almost all spend comes from the underlying agent's LLM calls and tool
work. The broker + idempotency overhead is typically < 1% of total cost.

---

## Per-Event Cost Breakdown

| Component                | Source                                          | Typical $ per 1k events |
|--------------------------|--------------------------------------------------|--------------------------|
| LLM calls (handler agent)| Input + output tokens × model price             | $0.30 - $4               |
| Tool calls               | Third-party APIs (Resy/OpenTable/Twilio/etc.)    | $0 - $1                  |
| Vector lookups (optional)| Embedding + query (per RAG sub-pattern)         | $0 - $0.10               |
| Broker ops               | Redis Streams `XREADGROUP` / `XACK` / `XADD`    | < $0.001                 |
| Idempotency store        | Redis `SETNX` + `GET` + final `SET`             | < $0.001                 |
| Outcome persistence      | One row insert (Postgres / Dynamo)              | < $0.001                 |

The pattern's overhead is essentially free at production token prices — the cost is the
underlying agent work. This is why event-driven scales well: doubling event volume
doubles handler cost (linear in LLM/tool spend) but only marginally increases broker /
state-store cost.

---

## Latency Breakdown

Single event, happy path:

| Stage                     | Typical | Notes                                                                |
|---------------------------|---------|----------------------------------------------------------------------|
| Broker dequeue            | 1-5ms   | `XREADGROUP COUNT N BLOCK` returns when events arrive or timeout     |
| Idempotency check         | 1-3ms   | Redis `SETNX` round-trip                                             |
| Handler agent run         | 0.5-3s  | Bulk of the time — LLM round-trip + tool calls                       |
| Persist outcome           | 5-20ms  | One DB insert                                                        |
| ACK                       | 1-2ms   | `XACK` round-trip                                                    |
| **Total**                 | ~1-5s   | Dominated by handler                                                 |

Retries multiply: a retry means re-dequeue (via `XCLAIM` after idle-ms) + idempotency
hit (cheap; dedupe on already-completed) OR full re-run if the prior attempt didn't
mark completion. Pending events idle for ~30s by default before `XCLAIM` re-delivers.

---

## What Drives Cost Up

- **Handler complexity.** The pattern overhead is fixed; the handler can be anything
  from a single Haiku classification ($0.0002/call) to a 5-turn Opus ReAct loop
  ($0.10+/call). Pick the model per handler — see
  `agent-deployments/docs/cross-cutting/model-routing.md`.
- **Failure-retry storms.** If a downstream is degraded, every event retries N times
  before going to DLQ. Each retry re-spends the handler's LLM cost. A circuit breaker
  per downstream (see `agent-deployments/docs/cross-cutting/resilience.md`) caps this.
- **Idempotency cache miss after expiry.** If TTL expires before re-delivery, a
  duplicate event is re-processed at full cost. Set TTL > broker's max redelivery
  window.
- **Replay storms after an incident.** A few thousand DLQ events replayed at once
  multiply handler cost. See the DLQ runbook
  (`agent-deployments/docs/cross-cutting/dlq-operations.md` § Runbook outline)
  for batched-replay-with-monitoring.

---

## What Drives Latency Up

- **Handler-side downstream slowness.** LLM provider throttling, third-party API
  latency, DB blip. The pattern's own overhead doesn't change.
- **Broker buffering when consumers are under-scaled.** Events sit in the stream
  longer; end-to-end latency = queue wait + handler time. Track `consumer.lag` as
  the queue-wait proxy.
- **Idempotency claim contention.** If two workers race for the same event (rare;
  partition-key based dispatch avoids it), one loses the claim and either retries or
  exits, doubling effective latency for that event.
- **Pending-entry reaper interval.** `XCLAIM` typically runs every 30s — an event
  whose consumer crashed mid-handler waits ~30s before another worker picks it up.

---

## Cost Control Knobs

**Right-size the handler model.** A classification step doesn't need Opus. Per-role
`model_hint` picks the cheapest model that meets quality. See
`agent-deployments/docs/cross-cutting/model-routing.md` per-role table.

**Cache the system prompt.** Event handlers typically reuse the same system prompt
across thousands of events per hour. Prompt-cache the stable prefix (1,024+ tokens)
for 5-min ephemeral or 1-hour persistent. Cache hits cut input cost ~10× and
materially flip the cost comparison Opus-with-cache vs Sonnet-no-cache.

**Cap retries at low N (3).** Each retry doubles the cost for that event class.
Letting permanent failures hit DLQ fast is cheaper than retrying for hours. Combine
with `agent-deployments/docs/cross-cutting/resilience.md` § Retries.

**Per-tenant budget guards.** A runaway producer or a poison-pill retry loop can
blow the LLM bill before it surfaces on dashboards. See
`agent-deployments/docs/cross-cutting/cost-tracking.md` for the per-tenant per-day
USD ceiling.

---

## Latency Control Knobs

**Scale consumers based on lag, not CPU.** KEDA / HPA on `consumer.lag` keeps tail
latency bounded as ingress varies. See
`agent-deployments/docs/cross-cutting/backpressure.md` § Adaptive scaling.

**Tune `XREADGROUP BLOCK`.** Block time too high (10s+) wastes latency at low load;
too low (< 100ms) burns CPU polling. 1-5s is typical.

**Use partition keys to avoid serialization bottlenecks.** Events with the same
partition key serialize through one consumer (preserving order); events with different
keys parallelize. Use `customer_id` or `restaurant_id` as the partition key when
per-entity ordering matters.

---

## Comparison to Related Patterns

| Pattern         | Est. LLM calls / invocation | Est. cost tier | Est. latency | Best when                                  |
|-----------------|-----------------------------|----------------|--------------|--------------------------------------------|
| Tool Use        | 2+ per round                | Low-Medium     | Low          | Synchronous request-driven function dispatch |
| Event-Driven    | 1-3 per event               | Medium         | Medium       | Async triggers, durable retry, scale-independent ingress |
| Multi-Agent     | N per request               | Medium-High    | Medium       | Parallel specialized agents on the same input |
| Plan-and-Execute| 2-5 per task                | Medium-High    | Medium-High  | Multi-step plans with intermediate checkpoints |
