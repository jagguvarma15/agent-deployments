# Cross-cutting: Rate Limiting

**Concern:** Protect agent endpoints from abuse with per-user and per-IP request throttling.
**Library:** `slowapi` (Py) / custom sliding-window middleware (TS)
**Lives in:** `common/python/agent_common/ratelimit/` and `common/typescript/src/ratelimit/`

## What it provides

- **Python:** `build_limiter(redis_url, default_limit)` returns a configured `slowapi.Limiter` instance backed by Redis. Integrates with FastAPI via `app.state.limiter` and the `@limiter.limit()` decorator.
- **TypeScript:** `buildRateLimiter(config)` returns a function `(key: string) => RateLimitResult` that checks a sliding window counter. Currently in-memory; swap to Redis for distributed deployments.

## How to use

### Python (FastAPI + slowapi)

```python
from agent_common.ratelimit import build_limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

limiter = build_limiter(redis_url="redis://localhost:6379", default_limit="60/minute")

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/query")
@limiter.limit("30/minute")  # Override default for this endpoint
async def query(request: Request):
    ...
```

The key function defaults to `get_remote_address` (client IP). For per-user limiting, pass a custom key function that extracts the user ID from the JWT.

### TypeScript (Hono)

```typescript
import { buildRateLimiter } from "@agent-deployments/common";

const checkLimit = buildRateLimiter({
  redisUrl: "redis://localhost:6379",
  maxRequests: 60,
  windowSeconds: 60,
});

app.use("*", async (c, next) => {
  const key = c.req.header("x-user-id") ?? c.req.header("x-forwarded-for") ?? "anon";
  const result = checkLimit(key);

  if (!result.allowed) {
    return c.json({ error: "Rate limit exceeded" }, 429);
  }

  c.header("X-RateLimit-Remaining", String(result.remaining));
  await next();
});
```

## Configuration via env

| Var | Default | Effect |
|-----|---------|--------|
| `REDIS_URL` | `redis://localhost:6379` | Redis instance for rate limit counters (Py) |
| Default limit | `60/minute` | Global default; override per-endpoint |

## Suggested limits for agent endpoints

| Endpoint type | Suggested limit | Rationale |
|--------------|----------------|-----------|
| `/query` (LLM call) | 10-30/minute | LLM calls are expensive and slow |
| `/documents` (ingest) | 5/minute | Ingestion triggers chunking + embedding |
| `/health` | Unlimited | Monitoring probes |

## Tests

- **Python:** `common/python/tests/test_ratelimit.py` -- limiter creation with Redis URL
- **TypeScript:** `common/typescript/tests/ratelimit.test.ts` -- window behavior, allow/deny, reset

## Production considerations

- The Python implementation is **production-ready** -- slowapi + Redis handles distributed rate limiting across multiple app instances.
- The TypeScript implementation is **in-memory** -- fine for single-instance dev, but must be swapped to a Redis-backed store (e.g., `hono-rate-limiter` with `ioredis`) for multi-instance production.
- Add `Retry-After` and `X-RateLimit-*` headers so clients can back off gracefully.
