---
id: cache.redis
kind: cache
implements:
  port: cache
  interface_version: "1.0"
layer: infrastructure
provides: [cache, session_store, rate_limit_backend]
env_vars: [REDIS_URL]
docker:
  service: redis
  image: redis:7-alpine
  ports: ["6379:6379"]
  volumes: ["redis_data:/data"]
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 5s
    timeout: 5s
    retries: 5
probe: redis_ping
bootstrap_step: null
provisioning_time: instant
cost_tier: free
est_tokens: 650
card:
  name: Redis
  description: "Redis 7 in-memory key-value store with Streams, hashes, and pub/sub."
  capabilities_provided: [cache, session_store, rate_limit_backend, event_source]
  required_credentials: []
emit_files: []
docs: |
  Redis 7 for cache, session storage, rate-limit counters, and (via Streams)
  low-throughput event source. No post-up bootstrap needed.
tags: [cache, in-memory, rate-limiting, session-store]
when_to_load: "recipe declares cache.redis"
stack_docs:
  - stack/cache-redis.md
---

# Capability: cache.redis

> Deep reference: [`stack/cache-redis.md`](../../stack/cache-redis.md). This page is the provisioning contract.

**Used for:** rate-limit backend, session cache, transient agent state, optional event source via Streams.

## Local setup

The docker fragment above is merged into `docker-compose.yml`. Redis-cli probe runs `PING` on the container.

## Bootstrap

None. Redis needs no post-up initialization for cache / session-store workloads. For Streams as an event source, pair this capability with [`queue.redis-streams`](../queue/redis-streams.md), which adds stream + consumer-group creation.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `REDIS_URL` | `redis://localhost:6379` | Connection string used by all clients |

## Client integration

**Python (redis-py async):**

```python
import redis.asyncio as redis
r = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

await r.set("session:abc123", json.dumps({"user_id": 42}), ex=3600)
session = json.loads(await r.get("session:abc123"))
```

**TypeScript (ioredis):**

```ts
import Redis from "ioredis";
const r = new Redis(process.env.REDIS_URL!);

await r.set("session:abc123", JSON.stringify({ userId: 42 }), "EX", 3600);
const session = JSON.parse((await r.get("session:abc123"))!);
```

## Sandbox vs managed

By default this capability runs Redis as an **in-sandbox container** — `REDIS_URL`
defaults to `redis://localhost:6379` and the compose fragment supplies it, so the
agent works with no credentials.

To point the agent at a **managed Redis** instead (Upstash, Redis Enterprise
Cloud, AWS ElastiCache), set `REDIS_URL` to the provider's connection string —
same shape, with two common additions:

| Concern | Sandbox | Managed |
|---------|---------|---------|
| Scheme  | `redis://` | `rediss://` (TLS — most managed providers require it) |
| Auth    | none | `:<password>@` (or `<user>:<password>@`) before the host |
| Example | `redis://localhost:6379` | `rediss://:s3cr3t@my-db.upstash.io:6380` |

In the scaffold REPL, connect one over the sandbox default with the secure
config entry: `/config REDIS_URL`. The value is exported to the run env and
`up` forwards it; the in-sandbox container is simply unused.

- **Self-hosted at scale** — Redis Sentinel for HA; Redis Cluster for sharded throughput. Enable `appendonly yes` if you cannot tolerate event loss on restart.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `connection refused 6379` | Container not up yet | `docker compose logs redis` — wait for "Ready to accept connections" |
| `OOM command not allowed when used memory > 'maxmemory'` | Memory cap reached | Bump `maxmemory` via Compose env; review TTLs and eviction policy |
| `NOAUTH Authentication required` | `REDIS_URL` missing password component | Add `:password@` segment to the URL (cloud Redis usually requires it) |
| `WRONGTYPE Operation against a key holding the wrong kind of value` | Same key reused across data types | Use distinct key prefixes per type (`session:*`, `stream:*`, `cache:*`) |

## See also

- [`stack/cache-redis.md`](../../stack/cache-redis.md) — full reference, Streams operations
- [`capabilities/queue/redis-streams.md`](../queue/redis-streams.md) — Streams as an event source
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
