# Cross-cutting: Backpressure

**Concern:** Keep producers, queues, and consumers in balance so the system fails predictably under overload instead of running out of memory, disk, or worker pool.
**Library:** `asyncio.Semaphore` / `asyncio.Queue` + broker config (Py) / `p-limit` + broker config (TS)
**Lives in:** Inline below — apply at the consumer boundary per recipe.

## What it provides

Five composable mechanisms to keep the work rate in line with the system's capacity:

1. **Bounded queues / streams** — cap how much unprocessed work can pile up; publishers block or drop when full.
2. **Pull-based consumption** — consumer requests N messages at a time; never pushed unbounded volume.
3. **Concurrency caps** — limit in-flight handlers per consumer (semaphore / worker pool).
4. **Adaptive scaling** — vary consumer count based on observed lag (HPA on lag metric).
5. **Explicit shedding** — drop low-priority work intentionally when overloaded; never silently.

Pick at least one upstream of every event-driven consumer. Pick all five for production at scale.

## Why this exists

Event-driven consumers (Redis Streams, Kafka, SQS, RabbitMQ) decouple producers from consumers — which is exactly why a backpressure plan matters. Without one, a slow downstream lets the queue grow unbounded; memory fills, disk fills, and the system either OOMs the consumer or fills the broker. By the time it surfaces, recovery means dropping data.

The opposite extreme — drop every message past a low watermark — sheds work the system could have handled. The mechanisms below give you knobs to bound resource use *and* surface the bound clearly so it shows up in metrics before it shows up as an incident.

## Symptoms

How to know you have a backpressure problem:

- **Consumer lag growing monotonically** — `XLEN` rising, Kafka `consumer_lag` ticking up, SQS `ApproximateNumberOfMessagesVisible` climbing.
- **Processing latency rising while ingress is flat** — workers spending longer per message; downstream is the bottleneck.
- **P99 climbing while P50 stays flat** — long-tail handlers stuck waiting on a saturated downstream.
- **Retries piling up** — events failing, retrying, failing again, never draining.
- **Memory or disk pressure on the broker or the consumer** — the queue itself is now the problem.

Page on lag > N for > T minutes. The lag metric is the single most useful signal — wire it before anything else.

## Mechanisms

### 1. Bounded queues / streams

Cap the maximum unprocessed depth. Either the publisher blocks (back-propagating pressure to the upstream) or the broker drops oldest/newest per policy.

In-process (Python `asyncio.Queue`):

```python
import asyncio

# maxsize=1000 → put() awaits when full → publisher feels the pressure
work_queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=1000)

async def producer(events: AsyncIterator[Event]) -> None:
    async for event in events:
        await work_queue.put(event)  # blocks when full

async def consumer() -> None:
    while True:
        event = await work_queue.get()
        await handle(event)
        work_queue.task_done()
```

At the broker, see "Per-broker specifics" below for `XADD MAXLEN`, Kafka segment retention, RabbitMQ queue length limits.

### 2. Pull-based consumption

The consumer asks for the next N messages on its own schedule; the broker never pushes more than the consumer requested. This is the default for Redis Streams `XREADGROUP COUNT N` and Kafka `poll(max_records=N)`. Avoid push-based fan-out protocols (raw Redis Pub/Sub, naive WebSocket fan-out) for work queues — there's no flow control.

### 3. Concurrency caps

Limit in-flight handlers per consumer so a slow downstream can't fan out into unbounded coroutines:

```python
import asyncio

handler_sem = asyncio.Semaphore(50)  # never more than 50 in flight per consumer

async def handle_with_cap(event: Event) -> None:
    async with handler_sem:
        await handle(event)
```

```typescript
import pLimit from "p-limit";

const limit = pLimit(50);
await limit(() => handle(event));
```

Pairs with [resilience.md § Bulkheads](resilience.md#bulkheads) — bulkheads are the per-dependency variant of this same concurrency cap.

### 4. Adaptive scaling

When lag exceeds a target, scale consumer count up. When lag drops below a floor, scale down. Two layers:

- **Worker-pool scale within a single consumer process** — grow the in-process worker count between a min and max.
- **Pod-level autoscale** — Kubernetes HPA driven by a custom metric (Redis Streams lag, Kafka `consumer_lag`). KEDA is the standard for queue-driven HPA.

Always cap the upper bound. "Scale to handle any load" turns a runaway producer or a poison-pill loop into an unbounded bill.

### 5. Explicit shedding

When all other mechanisms are saturated, shed work *visibly*:

- **HTTP layer** — return `503 Service Unavailable` with `Retry-After`. Don't silently queue.
- **Queue layer** — route low-priority work to a separate stream/topic the consumer can pause or drain selectively. Resy availability scans during an overload pause; reservation modifications keep flowing.
- **Always emit a metric** for every shed event. Silent drops are how you lose data and never find out.

## Per-broker specifics

### Redis Streams

```python
# Cap stream length to ~1M entries; oldest evicted when exceeded.
await client.xadd("events:rebook", payload, maxlen=1_000_000, approximate=True)

# Pull-based read: at most 100 at a time, block up to 5s for new entries.
entries = await client.xreadgroup(
    groupname="rebookers",
    consumername=consumer_id,
    streams={"events:rebook": ">"},
    count=100,
    block=5000,
)
```

Lag signal: `XLEN events:rebook` minus the consumer group's last-delivered-id position. Pending entries: `XPENDING events:rebook rebookers` (long-pending entries usually mean a stuck consumer).

### Kafka

```python
consumer = KafkaConsumer(
    "events.rebook",
    bootstrap_servers="kafka:9092",
    group_id="rebookers",
    max_poll_records=100,           # cap per poll batch
    max_poll_interval_ms=300_000,   # if a poll takes longer, leave the group
    enable_auto_commit=False,       # commit explicitly after work succeeds
)

for batch in consumer:
    # If downstream saturates, pause partitions so the broker doesn't keep
    # buffering for this consumer.
    if downstream_saturated():
        consumer.pause(consumer.assignment())
```

Lag signal: Kafka exporter's `kafka_consumergroup_lag` metric.

### RabbitMQ

```python
await channel.basic_qos(prefetch_count=50)  # never more than 50 unacked per consumer

async for message in channel.consume(queue="rebook"):
    try:
        await handle(message.body)
        await message.ack()
    except Exception:
        await message.nack(requeue=True)
```

The `prefetch_count` is the most important RabbitMQ backpressure knob — its default of "unlimited" is wrong for every production consumer. Pair with manual acks (`enable_auto_commit=False` equivalent) so a crash mid-handler re-queues the message.

## Composition with other patterns

- **With [resilience.md](resilience.md)** — when a downstream's circuit breaker opens, the consumer's effective throughput drops. Feed that into your shedding policy: while the breaker is Open, route low-priority work to a slow lane or shed it outright. The breaker tells you *which* dependency is bad; backpressure tells you *what to do about the work that needs it*.
- **With [multi-tenancy.md](multi-tenancy.md)** — per-tenant quotas prevent one tenant from consuming all available concurrency. A noisy tenant should hit *their* quota's wall before they push the shared queue into overflow.
- **With cost-tracking** — for LLM-heavy work, a per-tenant cost ceiling acts as a form of backpressure: once a tenant burns through their budget, their work routes to a slow lane or fails fast. Cost is a finite resource just like memory and worker slots.
- **With [observability.md](observability.md)** — every mechanism above must emit metrics: queue depth, in-flight count, shed count, lag. Without them, backpressure is invisible until it fails.

## Tests

- **Saturate test** — produce 10× the consumer's capacity for a fixed window; assert: queue depth hits the cap, no OOM, lag metric crosses the alert threshold, shed-count metric increments.
- **Drain test** — let producer pause; assert lag returns to zero within an expected drain window.
- **Crash-while-saturated test** — kill a consumer while the queue is full; assert another consumer in the group picks up pending entries (`XPENDING` non-zero recovers to zero).

## Pitfalls

- **Unbounded `asyncio.Queue`** — the default `maxsize=0` is "infinite." Always set a cap. Pair with a metric on `queue.qsize()`.
- **Auto-scaling without an upper bound** — KEDA / HPA with no max replicas turns a runaway producer into an unbounded compute bill.
- **Silent drops** — every shed event must increment a counter. "We thought we were keeping up" is the post-mortem you don't want.
- **Retrying immediately into a saturated downstream** — pairs with [resilience.md § Retries](resilience.md#retries); if the breaker is closed but the downstream is slow, immediate retries amplify load. Backoff + breaker handle this together.
- **One global queue for many priorities** — high-priority work waits behind low-priority backlog. Separate queues (or priority routing) let you shed selectively.
- **Treating lag as the only signal** — lag can be low while *processing latency* is high (each message taking longer). Watch both.
- **Auto-ack on the broker side** — RabbitMQ / Kafka `enable_auto_commit=True` ACKs before the work completes, so a crash mid-handler loses the message. Manual ack always.

## Where used in repo

- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — Redis Streams consumer with `XADD MAXLEN ~ 1M` cap, `XREADGROUP COUNT 100 BLOCK 5000` pull-based reads, in-process semaphore concurrency cap, per-platform shed lane (when one platform's breaker opens, search work for that platform routes to a slow lane). KEDA on `xlen(events:rebook)` for pod scaling.
