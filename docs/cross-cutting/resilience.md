# Cross-cutting: Resilience

**Concern:** Handle transient failures, slow dependencies, and partial outages without taking down the whole system.
**Library:** `tenacity` + `pybreaker` + `httpx` (Py) / `p-retry` + `opossum` (TS)
**Lives in:** Inline below — wrap dependency-facing calls per recipe.

## What it provides

Four composable building blocks. Apply them at the dependency boundary (the function that calls the third-party API, the DB, the LLM):

1. **Retries** -- re-attempt after transient failures, with exponential backoff and jitter.
2. **Timeouts** -- cap the wait on each dependency call so a slow downstream doesn't pin a worker.
3. **Circuit breakers** -- stop calling a known-bad dependency for a cooldown period so it can recover.
4. **Bulkheads** -- isolate concurrency budgets per dependency so one slow downstream can't drown the others.

These compose in a specific order: bulkhead → timeout → retry → circuit breaker. Get the order wrong (e.g., retry outside the circuit breaker) and you'll defeat the breaker on every failure burst.

## Why this exists

Every production system talks to dependencies that fail intermittently — LLM APIs throttle, third-party platforms 502, DBs blip during failover. Without resilience, every blip becomes a user-visible failure and every slow dependency becomes a worker-pool exhaustion incident.

The opposite extreme — retry-everything, unbounded timeout — turns a 30-second outage into a 30-minute cascade. The four patterns below are the minimum kit to fail well.

## Retries

### When to retry vs not

| Retry | Don't retry |
|-------|-------------|
| 5xx responses | 4xx (except 408, 429) |
| Connection errors, DNS, TLS handshake | Validation errors, malformed payloads |
| Read/write timeouts | `409 Conflict` / "already exists" |
| `429 Too Many Requests` (with backoff) | Auth failures (401, 403) — fix the credential, don't retry |

Retrying a 4xx is at best wasted budget and at worst hides a bug.

### Backoff strategy

Exponential backoff with full jitter. Constant or linear backoff causes thundering-herd retries that knock the dependency back over the moment it recovers.

```python
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=30),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
    reraise=True,
)
async def call_platform_api(client: httpx.AsyncClient, payload: dict) -> dict:
    resp = await client.post("/reservations", json=payload, timeout=10.0)
    resp.raise_for_status()
    return resp.json()
```

```typescript
import pRetry, { AbortError } from "p-retry";

export async function callPlatformApi(payload: unknown): Promise<unknown> {
  return pRetry(
    async () => {
      const resp = await fetch("/reservations", {
        method: "POST",
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(10_000),
      });
      if (resp.status >= 400 && resp.status < 500 && resp.status !== 408 && resp.status !== 429) {
        throw new AbortError(`non-retryable ${resp.status}`);
      }
      if (!resp.ok) throw new Error(`upstream ${resp.status}`);
      return resp.json();
    },
    { retries: 5, factor: 2, minTimeout: 1_000, maxTimeout: 30_000, randomize: true },
  );
}
```

### Combine with idempotency

Retries are **only safe** when the called operation is idempotent. If you retry a non-idempotent POST you can write the row twice. Always pair this with [idempotency.md](idempotency.md) — pass `Idempotency-Key` on outbound calls and dedupe on inbound events.

### Honour `Retry-After`

For `429` and `503`, the upstream may tell you when to come back via the `Retry-After` header. Prefer that over your local backoff.

## Timeouts

### Layered timeouts

| Layer | Typical | Purpose |
|-------|---------|---------|
| Connect timeout | 1–3 s | TCP handshake + TLS. Fast detection of unreachable hosts. |
| Read timeout | 5–30 s | Wait for the response body. Depends on endpoint cost. |
| Write timeout | 1–5 s | Sending the request body. |
| Total operation cap | hard ≤ 60 s | All retries + waits combined, enforced by the caller. |

`httpx.Timeout` exposes all four; the default of "no timeout" is the wrong choice for every production code path:

```python
import httpx

client = httpx.AsyncClient(
    timeout=httpx.Timeout(connect=2.0, read=10.0, write=5.0, pool=2.0),
)
```

### Total-time cap on top of retries

`tenacity`'s `stop_after_delay` caps wall-clock time across all retry attempts:

```python
from tenacity import stop_after_delay, stop_after_attempt

# Stop on whichever happens first: 60s total or 5 attempts
@retry(stop=stop_after_delay(60) | stop_after_attempt(5), ...)
async def call_with_hard_cap(...): ...
```

Without a total cap, a sequence of slow attempts can blow far past the per-call timeout — five 10-second timeouts plus exponential backoff is over a minute, and you may need to ACK an upstream message well before then.

## Circuit breakers

Stop hammering a dependency that's clearly down. The breaker has three states:

- **Closed** -- calls pass through; failures are counted.
- **Open** -- calls fail fast for `reset_timeout` seconds. No requests reach the dependency.
- **Half-open** -- one probe call is allowed; success → Closed, failure → Open.

```python
import pybreaker
import httpx

platform_breaker = pybreaker.CircuitBreaker(
    fail_max=5,                                    # open after 5 consecutive failures
    reset_timeout=60,                              # try one probe after 60s
    exclude=[httpx.HTTPStatusError],               # 4xx shouldn't trip the breaker
    name="reservation_platform",
)

@platform_breaker
async def modify_reservation(payload: dict) -> dict:
    return await call_platform_api(client, payload)
```

```typescript
import CircuitBreaker from "opossum";

const breaker = new CircuitBreaker(modifyReservationInner, {
  timeout: 10_000,
  errorThresholdPercentage: 50,
  resetTimeout: 60_000,
  name: "reservation_platform",
});
breaker.fallback(() => ({ status: "deferred" })); // optional
```

When the breaker is open, the caller gets a typed exception (`CircuitBreakerError` / `breaker.opened` event). Route it to a fallback path, a DLQ, or surface a clear error — never silently swallow.

### Tuning

- `fail_max` too low → flaps on transient blips. Start at 5, raise if noisy.
- `reset_timeout` too short → re-opens immediately. Start at 60s, tune to recovery shape.
- Exclude business 4xx from counting as failures — they're application logic, not dependency health.

## Bulkheads

Cap concurrent calls per dependency so a slow one can't exhaust your event loop or thread pool. The simplest implementation is a semaphore per outbound dependency:

```python
import asyncio

notification_sem = asyncio.Semaphore(20)
platform_sem    = asyncio.Semaphore(50)

async def notify(customer_id: str, body: str) -> None:
    async with notification_sem:
        await call_notification_api(customer_id, body)

async def rebook(reservation_id: str) -> None:
    async with platform_sem:
        await call_platform_api(...)
```

```typescript
import pLimit from "p-limit";

const notifyLimit   = pLimit(20);
const platformLimit = pLimit(50);

await notifyLimit(() => callNotificationApi(customerId, body));
await platformLimit(() => callPlatformApi(...));
```

Without bulkheads, a notification provider that suddenly slows to 30s/request will fill all 100 of your async tasks, and platform calls (which are fine) will queue behind them. With bulkheads, the slow dependency caps out at its own 20-slot budget while platform calls keep flowing.

## Combining them

Order matters. Apply outward-in from the dependency:

```
caller
  └─ bulkhead     (semaphore — limits concurrent in-flight calls)
       └─ circuit breaker  (fail fast if dependency is known-bad)
            └─ retry            (exponential backoff with jitter)
                 └─ timeout         (cap each individual attempt)
                      └─ dependency call
```

Why this order:

- **Bulkhead outermost** — even retried calls count against the concurrency budget.
- **Breaker before retries** — an open breaker should short-circuit retries entirely, not retry through them.
- **Retry inside timeout** — each attempt gets the same per-call timeout; the outer `stop_after_delay` caps the total.

```python
@platform_sem_decorator(20)        # bulkhead
@platform_breaker                   # circuit breaker
@retry(stop=stop_after_delay(60) | stop_after_attempt(5),
       wait=wait_exponential_jitter(initial=1, max=30),
       retry=retry_if_exception_type(TransientError),
       reraise=True)
async def modify_reservation(payload: dict) -> dict:
    return await client.post(..., timeout=10.0)  # per-attempt timeout
```

## Tests

- **Retry test** -- monkeypatch the dependency to fail N-1 times then succeed; assert the call returns after exactly N attempts.
- **Non-retry test** -- raise a `ValueError`; assert no retry.
- **Timeout test** -- inject a `sleep` longer than the read timeout; assert `TimeoutException`.
- **Breaker test** -- force `fail_max` consecutive failures; assert the next call raises `CircuitBreakerError` without invoking the dependency.
- **Bulkhead test** -- launch `limit + 5` concurrent calls; assert no more than `limit` are in flight at once.

## Pitfalls

- **No total cap** — five 10-second timeouts + exponential backoff = minute-plus tail latency.
- **Retrying non-idempotent operations** — double writes. Always pair with idempotency keys.
- **Breaker excluding nothing** — every 404 trips it, breaker opens during normal use.
- **Bulkhead per request instead of per dependency** — defeats the point; you wanted to isolate downstreams.
- **Catching `Exception` in `retry_if_exception_type`** — retries auth errors, validation errors, OOMs. Be specific about what's transient.
- **Forgetting `reraise=True`** — `tenacity` wraps the last exception in `RetryError` by default; callers expecting the original type get confused.

## Where used in repo

- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — reservation platform adapter wraps each outbound call with retry + timeout + breaker; notification fan-out uses a semaphore bulkhead.
