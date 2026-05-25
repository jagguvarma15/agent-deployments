# Stack pick: Redis

> Standing Redis up for the first time? Start with [`getting-started/redis.md`](../getting-started/redis.md) for the one-screen quickstart. This doc is the deep reference.

**Choice:** Redis 7-alpine (or Valkey), self-hosted via Docker
**Used for:** Rate limiting backend, session cache, transient state

## Why this over alternatives

| Option | Why not |
|--------|---------|
| Memcached | No persistence, no pub/sub, simpler data structures |
| Valkey | Drop-in Redis replacement (MIT-licensed fork). Use interchangeably |
| DragonflyDB | Compatible API but less battle-tested; good alternative for high-throughput |

## Local setup

Defined in the [Docker Compose template](../reference/docker-compose-template.md):

```yaml
redis:
  image: redis:7-alpine
  ports:
    - "${REDIS_PORT:-6379}:6379"
  volumes:
    - redis_data:/data
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 5s
    timeout: 5s
    retries: 5
```

Connect locally: `redis-cli -h localhost -p 6379`

## Config knobs that matter

| Knob | Default | Effect |
|------|---------|--------|
| `REDIS_URL` | `redis://localhost:6379` | Connection string used by rate limiter and session store |
| `REDIS_PORT` | `6379` | Host port mapping |
| `maxmemory` | unlimited | Set a cap in production to prevent OOM |
| `maxmemory-policy` | `noeviction` | Use `allkeys-lru` for cache workloads |

## Integration pattern

### Python (rate limiting via slowapi)

```python
from agent_common.ratelimit import build_limiter

limiter = build_limiter(redis_url="redis://localhost:6379", default_limit="60/minute")
```

slowapi stores rate-limit counters in Redis automatically. No direct Redis client code needed.

### Python (direct access via redis-py)

```python
import redis.asyncio as redis

client = redis.from_url("redis://localhost:6379")
await client.set("session:user-1", '{"context": "..."}', ex=3600)
value = await client.get("session:user-1")
```

### TypeScript (via ioredis)

```typescript
import Redis from "ioredis";

const redis = new Redis("redis://localhost:6379");
await redis.set("session:user-1", JSON.stringify({ context: "..." }), "EX", 3600);
const value = await redis.get("session:user-1");
```

## Where used in repo

- **Rate limiting** -- `slowapi` (Py) uses Redis as its backing store for distributed counters
- **Docker Compose** -- see the `redis` service in [Docker Compose template](../reference/docker-compose-template.md)
- **Session state** -- available for agents that need transient conversation cache (not used by default; Postgres handles persistent state)

## Production considerations

- For multi-instance deployments, Redis is required for distributed rate limiting (the TS in-memory rate limiter won't work across instances).
- Enable Redis persistence (`appendonly yes`) if using Redis for anything beyond ephemeral cache.
- Consider Redis Sentinel or Redis Cluster for HA in production.

## Redis Streams as event source

Redis Streams (introduced in Redis 5) provides an append-only log with consumer groups — a lightweight alternative to Kafka for moderate-throughput event-driven systems. See the [Event-Driven Agents pattern](../patterns/event-driven.md) for the agent shape that consumes these streams.

### When to pick Redis Streams over Kafka

- You're already running Redis for cache/rate limiting (one less service).
- Throughput is ≤10k events/sec per stream.
- Retention of hours-to-days is sufficient (not weeks).
- You don't need cross-region replication built in.

### Stream operations

| Operation | Purpose |
|-----------|---------|
| `XADD <stream> * field val ...` | Append an event |
| `XGROUP CREATE <stream> <group> $` | Create a consumer group at the tail |
| `XREADGROUP GROUP <group> <consumer> COUNT n BLOCK ms STREAMS <stream> >` | Read new events |
| `XACK <stream> <group> <id>` | Acknowledge processed event |
| `XPENDING <stream> <group>` | Inspect unacknowledged events |
| `XCLAIM <stream> <group> <consumer> <min-idle-ms> <id>` | Reclaim stuck events from a dead consumer |

### Python (redis-py async)

```python
import redis.asyncio as redis

client = redis.from_url("redis://localhost:6379")

# Producer
await client.xadd("reservations.cancelled", {
    "event_id": "evt-123",
    "restaurant_id": "rest-99",
    "reservation_id": "res-42",
    "trace_id": "trace-abc",
    "payload": '{"party_size": 4, "time": "2026-05-21T19:30:00Z"}'
})

# Consumer (run as a long-lived loop)
await client.xgroup_create("reservations.cancelled", "rebooker", id="$", mkstream=True)
while True:
    msgs = await client.xreadgroup(
        groupname="rebooker", consumername="worker-1",
        streams={"reservations.cancelled": ">"},
        count=10, block=5000,
    )
    for stream, entries in msgs:
        for msg_id, fields in entries:
            try:
                await handle_event(fields)
                await client.xack(stream, "rebooker", msg_id)
            except RetryableError:
                pass  # leave un-ACKed; XCLAIM will pick it up after timeout
            except PermanentError:
                await client.xadd("reservations.cancelled.dlq", fields)
                await client.xack(stream, "rebooker", msg_id)
```

### TypeScript (ioredis)

```typescript
import Redis from "ioredis";
const redis = new Redis("redis://localhost:6379");

// Producer
await redis.xadd("reservations.cancelled", "*",
  "event_id", "evt-123",
  "restaurant_id", "rest-99",
  // ...
);

// Consumer
try { await redis.xgroup("CREATE", "reservations.cancelled", "rebooker", "$", "MKSTREAM"); } catch {}
while (true) {
  const msgs = await redis.xreadgroup(
    "GROUP", "rebooker", "worker-1",
    "COUNT", 10, "BLOCK", 5000,
    "STREAMS", "reservations.cancelled", ">",
  );
  // ... ACK / DLQ handling
}
```

### Idempotency with Redis SET

```python
seen = await client.set(f"idemp:{event_id}", "1", ex=86400, nx=True)
if not seen:
    return  # duplicate, already processed
```

### DLQ pattern

- Create a parallel stream `<topic>.dlq` for poison events.
- On permanent failure, `XADD` the original event payload + error metadata to the DLQ.
- Operationally: alert on DLQ depth; manually re-publish after fixes.

### Limits

- **Max length:** Use `MAXLEN ~ N` in `XADD` to cap stream size (approximate trimming is much faster).
- **Persistence:** Enable AOF (`appendonly yes`) if you cannot tolerate event loss on Redis restart.
- **Throughput:** Single-stream throughput is bounded by single-CPU performance. Shard across streams (by hash of partition key) for higher rates.
