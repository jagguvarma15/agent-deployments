---
id: queue.redis-streams
kind: queue
implements:
  port: queue
  interface_version: "1.0"
layer: infrastructure
requires: [cache.redis]
provides: [event_source]
env_vars: [REDIS_URL]
docker: null
probe: redis_ping
bootstrap_step: bootstrap_kafka
provisioning_time: instant
cost_tier: free
est_tokens: 550
card:
  name: Redis Streams
  description: "Redis Streams as the event source — log-shaped data type with consumer groups and ACK."
  capabilities_provided: [event_source, consumer_groups, replay_within_retention]
  required_credentials: []
emit_files: []
docs: |
  Redis Streams as the event source. Piggybacks on `cache.redis` — no extra
  service. Bootstrap step creates consumer groups (the `bootstrap_kafka`
  step name covers both Kafka topics and Redis Streams consumer groups).
tags: [queue, lightweight, redis]
when_to_load: "recipe declares queue.redis-streams"
verification:
  tier: T1
---

# Capability: queue.redis-streams

> Deep reference: [`stack/cache-redis.md`](../../stack/cache-redis.md#redis-streams-as-event-source) "Redis Streams as event source".

**Used for:** event source up to ~10k events/sec per stream, with hours-to-days retention.

## Local setup

**No docker fragment.** This capability requires `cache.redis` on the same recipe; the resolver enforces this and fails generation with a clear error otherwise.

## Bootstrap (post docker_up)

The `bootstrap_kafka` step (overloaded name — owns both Kafka topics and Redis Stream consumer groups) reads recipe frontmatter `streams:`:

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
| `REDIS_URL` | *(inherited from `cache.redis`)* | Connection string |

## Client integration

**Python (redis-py async):**

```python
import redis.asyncio as redis
r = redis.from_url(os.environ["REDIS_URL"])

# Producer
await r.xadd("events.in", {"payload": json.dumps({"id": 1})}, maxlen=10000, approximate=True)

# Consumer (group reader; processes new + pending)
async def consume():
    while True:
        msgs = await r.xreadgroup("workers", "consumer-1", {"events.in": ">"}, count=10, block=1000)
        for stream, entries in msgs:
            for entry_id, fields in entries:
                await process(json.loads(fields[b"payload"]))
                await r.xack("events.in", "workers", entry_id)
```

**TypeScript (ioredis):**

```ts
import Redis from "ioredis";
const r = new Redis(process.env.REDIS_URL!);

// Producer
await r.xadd("events.in", "MAXLEN", "~", 10000, "*", "payload", JSON.stringify({ id: 1 }));

// Consumer
while (true) {
  const msgs = await r.xreadgroup("GROUP", "workers", "consumer-1",
    "COUNT", 10, "BLOCK", 1000, "STREAMS", "events.in", ">");
  if (!msgs) continue;
  for (const [, entries] of msgs) {
    for (const [id, fields] of entries) {
      await process(JSON.parse(fields[1]));
      await r.xack("events.in", "workers", id);
    }
  }
}
```

## Cloud / production

Same hosting story as `cache.redis`. Enable `appendonly yes` for stream persistence; Streams are evicted under memory pressure otherwise.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `NOGROUP No such key 'X' or consumer group 'Y'` | Bootstrap didn't create the consumer group | Re-run `bootstrap_kafka`; or call `XGROUP CREATE ... MKSTREAM` |
| Stream loses messages on Redis restart | `appendonly no` (default) | Enable AOF persistence in Compose env |
| Consumer falls behind | Single consumer in a group with many entries | Scale consumers within the group; entries are partitioned by consumer-id |
| `BUSYGROUP Consumer Group name already exists` | Re-running bootstrap | Benign — bootstrap swallows this. If raised elsewhere, drop the group with `XGROUP DESTROY` first |

## See also

- [`stack/cache-redis.md`](../../stack/cache-redis.md) — Streams operations table, consumer code, DLQ pattern
- [`capabilities/cache/redis.md`](../cache/redis.md) — sibling cache capability
- [`patterns/event_driven/overview.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/patterns/event_driven/overview.md) — pattern this implements
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
