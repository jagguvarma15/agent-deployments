# Cross-cutting: Rate Limiting

**Concern:** Protect agent endpoints from abuse with per-user and per-IP request throttling.
**Library:** `slowapi` (Py) / custom sliding-window middleware (TS)
**Lives in:** Inline below (formerly `common/python/agent_common/ratelimit/` and `common/typescript/src/ratelimit/`)

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

Test limiter creation with Redis URL (Py). Test window behavior, allow/deny, and reset (TS).

## Production considerations

- The Python implementation is **production-ready** -- slowapi + Redis handles distributed rate limiting across multiple app instances.
- The TypeScript implementation is **in-memory** -- fine for single-instance dev, but must be swapped to a Redis-backed store (e.g., `hono-rate-limiter` with `ioredis`) for multi-instance production.
- Add `Retry-After` and `X-RateLimit-*` headers so clients can back off gracefully.

## Reference Implementation

<details>
<summary>Python — <code>slowapi_setup.py</code></summary>

```python
"""Rate limiter setup using slowapi + Redis."""

from slowapi import Limiter
from slowapi.util import get_remote_address


def build_limiter(
    redis_url: str = "redis://localhost:6379",
    *,
    default_limit: str = "60/minute",
) -> Limiter:
    """Build a configured slowapi Limiter backed by Redis."""
    return Limiter(
        key_func=get_remote_address,
        default_limits=[default_limit],
        storage_uri=redis_url,
    )
```

</details>

<details>
<summary>TypeScript — <code>ratelimit.ts</code></summary>

```typescript
/**
 * Rate limiting utilities for Hono-based prototypes.
 */

export interface RateLimitConfig {
  /** Redis URL for distributed rate limiting */
  redisUrl: string;
  /** Max requests per window */
  maxRequests: number;
  /** Window size in seconds */
  windowSeconds: number;
}

interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  resetAt: number;
}

/**
 * Build a rate limiter function.
 *
 * Returns a function that checks whether a given key (e.g., user ID or IP)
 * is within its rate limit. Uses a simple in-memory sliding window for now;
 * Redis-backed implementation should be added per prototype.
 */
export function buildRateLimiter(config: RateLimitConfig) {
  const windows = new Map<string, { count: number; resetAt: number }>();

  return (key: string): RateLimitResult => {
    const now = Date.now();
    const entry = windows.get(key);

    if (!entry || now >= entry.resetAt) {
      windows.set(key, {
        count: 1,
        resetAt: now + config.windowSeconds * 1000,
      });
      return {
        allowed: true,
        remaining: config.maxRequests - 1,
        resetAt: now + config.windowSeconds * 1000,
      };
    }

    entry.count++;
    const allowed = entry.count <= config.maxRequests;
    return {
      allowed,
      remaining: Math.max(0, config.maxRequests - entry.count),
      resetAt: entry.resetAt,
    };
  };
}
```

</details>
