---
id: queue.redis-streams
kind: queue
provides: [event_source]
env_vars: [REDIS_URL]
docker: null
probe: redis_ping
bootstrap_step: bootstrap_kafka
emit_files: []
docs: |
  Redis Streams as the event source. Piggybacks on `cache.redis` — no extra
  service. Bootstrap step creates consumer groups (the `bootstrap_kafka` step
  handles both Kafka topics and Redis Streams consumer groups).
---

# Capability: queue.redis-streams

> Deep reference: [`stack/cache-redis.md` "Redis Streams as event source"](../../stack/cache-redis.md#redis-streams-as-event-source).

**Used for:** event source up to ~10k events/sec per stream, with hours-to-days retention.

## Why pick this

When you're already running `cache.redis` and your event-source needs fit inside its envelope. Zero new infrastructure, one stream-creation call, full event-driven agent shape (consumer groups, ACK, XCLAIM for stuck consumers).

## Local setup

**No docker fragment.** This capability requires `cache.redis` on the same recipe; the resolver enforces this and fails generation with a clear error otherwise.

## Bootstrap (post docker_up)

The `bootstrap_kafka` step (despite the name — it owns both Kafka topics and Redis Stream consumer groups) reads recipe frontmatter `streams:`:

```python
import redis.asyncio as redis
client = redis.from_url(os.environ["REDIS_URL"])
for stream in streams:
    try:
        await client.xgroup_create(
            stream["name"], stream["consumer_group"], id="$", mkstream=True
        )
    except redis.ResponseError as e:
        if "BUSYGROUP" not in str(e):  # already exists is fine
            raise
```

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `REDIS_URL` | *(inherited from cache.redis)* | Connection string |

## Cloud / production

Same hosting story as `cache.redis`. Enable `appendonly yes` for stream persistence; Streams are evicted under memory pressure otherwise.

## When to swap it

- **→ `queue.kafka`** when throughput exceeds ~5k events/sec sustained per stream, OR retention needs exceed days, OR multi-team schema governance becomes important.

## See also

- `stack/cache-redis.md` — Streams operations table, consumer code, DLQ pattern
- `capabilities/cache/redis.md` — sibling cache capability
- `patterns/event-driven.md` — pattern this implements
