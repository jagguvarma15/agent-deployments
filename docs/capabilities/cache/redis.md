---
id: cache.redis
kind: cache
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
emit_files: []
docs: |
  Redis 7 for cache, session storage, and rate-limit counters. No post-up
  bootstrap needed — `docker compose up` is sufficient.
---

# Capability: cache.redis

> Deep reference: [`stack/cache-redis.md`](../../stack/cache-redis.md). This page is the provisioning contract.

**Used for:** rate-limit backend, session cache, transient agent state, optional event source via Streams.

## Why pick this

Default cache pick. One container, one port, one volume. Doubles as a rate-limit backend (slowapi / express-rate-limit), a session store, and — via Streams — a low-throughput event source. Most agents that need any kind of ephemeral key-value state want this.

## Local setup

The docker fragment above is merged into `docker-compose.yml`. Redis-cli probe runs `PING` on the container.

## Bootstrap

None. Redis needs no post-up initialization for cache / session-store workloads. If you're using Redis Streams as the event source, pair this capability with `queue.redis-streams`, which adds stream + consumer-group creation.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `REDIS_URL` | `redis://localhost:6379` | Connection string used by all clients |

## Cloud / production

- **Managed** — Upstash, Redis Enterprise Cloud, AWS ElastiCache. Same `REDIS_URL` shape.
- **Self-hosted at scale** — Redis Sentinel for HA; Redis Cluster for sharded throughput. Enable `appendonly yes` if you cannot tolerate event loss on restart.

## When to swap it

- **→ Valkey** drop-in (Redis fork, MIT-licensed) — same env var, same client libraries.
- **→ DragonflyDB** for higher-throughput single-node workloads.

Capability id stays `cache.redis` for both — substitution happens at image-tag level in a recipe override, not at capability level.

## See also

- `stack/cache-redis.md` — full reference including Redis Streams operations
- `capabilities/queue/redis-streams.md` — Streams as an event source
