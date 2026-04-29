# Stack pick: Redis

**Choice:** Redis 7-alpine (or Valkey), self-hosted via Docker
**Used for:** Rate limiting backend, session cache, transient state

## Why this over alternatives

| Option | Why not |
|--------|---------|
| Memcached | No persistence, no pub/sub, simpler data structures |
| Valkey | Drop-in Redis replacement (MIT-licensed fork). Use interchangeably |
| DragonflyDB | Compatible API but less battle-tested; good alternative for high-throughput |

## Local setup

Defined in `common/docker-compose.base.yml`:

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
- **Docker Compose** -- every prototype extends the `redis` service from `common/docker-compose.base.yml`
- **Session state** -- available for prototypes that need transient conversation cache (not used by default; Postgres handles persistent state)

## Production considerations

- For multi-instance deployments, Redis is required for distributed rate limiting (the TS in-memory rate limiter won't work across instances).
- Enable Redis persistence (`appendonly yes`) if using Redis for anything beyond ephemeral cache.
- Consider Redis Sentinel or Redis Cluster for HA in production.
