# Redis

> In-memory data store. Used as the rate-limiter backend, session cache, idempotency key store, and (with Streams) the event source for event-driven recipes.

**Signup**: not required for local Docker; hosted options below.

## Quick install (local Docker)

```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

Stop / restart later:

```bash
docker stop redis && docker start redis
```

## Hosted alternatives

| Provider | Free tier | Quickstart |
|----------|-----------|------------|
| Upstash | 10k commands/day, 256MB | https://upstash.com/docs/redis/overall/getstarted |
| Redis Cloud | 30MB, 30 connections | https://redis.io/cloud/ |
| Render | 25MB | https://render.com/docs/redis |
| AWS ElastiCache | none (paid) | regional VPC setup |

For dev work, prefer local Docker. Hosted Redis matters when you need persistence guarantees across redeploys.

## Verify

```bash
redis-cli -h localhost -p 6379 ping     # → PONG
# or, without the client:
nc -z localhost 6379 && echo "reachable"
```

## Wire into your project

Set in `.env.local`:

```
REDIS_URL=redis://localhost:6379/0
```

For a hosted instance with auth: `redis://default:<password>@<host>:<port>/0` (note the `default` user with Upstash / Redis Cloud).

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Connection refused` | Daemon not running | `docker start redis` (or `docker run` again) |
| `NOAUTH Authentication required` | URL missing `:password@` part | Add the password from your provider console |
| `OOM command not allowed when used memory > 'maxmemory'` | Memory cap reached | Bump `maxmemory` on the server; review TTLs |
| `WRONGTYPE Operation against a key holding the wrong kind of value` | Key reused across stream / hash / string | Use distinct key prefixes per data type |

## See also

- [`docs/stack/cache-redis.md`](../stack/cache-redis.md) — full config, AOF/RDB persistence, eviction policies
- [`patterns/event_driven/overview.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/patterns/event_driven/overview.md) — Redis Streams as the event source
