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

### When to use

Reach for a breaker on every external networked call: third-party APIs, downstream microservices, LLM provider HTTPS, message brokers, distributed caches. Skip it for in-process pure functions and local SQLite — there's no recovery state to model. A breaker around a Python function is just an exception handler with extra steps.

Rule of thumb: if the call leaves the network stack and the dependency has a non-trivial baseline failure rate, wrap it. If not, don't.

Threshold examples, by call class:

| Call class | Trip condition |
|------------|----------------|
| High-volume APIs (LLM provider, primary reservation platform) | `failure_rate > 50%` over a 30s window, OR 5 consecutive failures |
| Low-volume APIs (admin endpoints, batch hooks) | 3 consecutive failures — not enough samples for rate-based detection |
| Databases | Usually leave to the connection pool's reconnect logic; reach for a breaker only when DB issues cascade into worker-pool exhaustion |

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

### Per-service vs global

Every external dependency gets its **own** breaker. Resy's breaker is independent of OpenTable's, which is independent of Toast's. Never wrap multiple distinct dependencies under one breaker — a Resy outage would also block calls to OpenTable, defeating the point of having multiple platforms.

```python
resy_breaker      = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60, name="resy")
opentable_breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60, name="opentable")
toast_breaker     = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60, name="toast")
```

```typescript
const resyBreaker      = new CircuitBreaker(resyCall,      { ...defaults, name: "resy" });
const opentableBreaker = new CircuitBreaker(opentableCall, { ...defaults, name: "opentable" });
const toastBreaker     = new CircuitBreaker(toastCall,     { ...defaults, name: "toast" });
```

If a single downstream has endpoints with materially different failure modes (e.g. `/search` is fragile but `/cancel` is solid), give them separate breakers so a `/search` outage doesn't suspend cancellations.

### Fallback semantics

When the breaker is open, the caller can't reach the dependency. Pick one of four responses based on what the call class actually needs:

| Response | When to use | Rebooking example |
|----------|-------------|-------------------|
| **Return cached value** | Read-mostly endpoints with tolerable staleness | "Get current reservation status" — serve last-known status with a `stale=true` flag |
| **Return degraded result** | The caller can act with less info | Search across 3 platforms; one is open → return results from the 2 healthy ones with a warning |
| **Queue for retry-later** | Write that must eventually land, no rush | Confirmation SMS — enqueue to a retry job that drains when the breaker closes |
| **Fail fast** | The operation can't safely proceed without this dependency | Modify a reservation on the specific platform that's down — surface a clear typed error to the caller |

```python
@platform_breaker
async def modify_reservation(payload: dict) -> dict:
    return await call_platform_api(payload)

async def safe_modify(payload: dict) -> dict:
    try:
        return await modify_reservation(payload)
    except pybreaker.CircuitBreakerError:
        await enqueue_retry(payload, reason="platform_breaker_open")
        return {"status": "deferred", "retry_after": 60}
```

Never silently swallow `CircuitBreakerError`. Either map it to a typed business response (`{"status": "deferred"}`) or re-raise — the call must look different from a normal success.

### Tuning

- `fail_max` too low → flaps on transient blips. Start at 5, raise if noisy.
- `reset_timeout` too short → re-opens immediately. Start at 60s, tune to recovery shape.
- Exclude business 4xx from counting as failures — they're application logic, not dependency health.

### Observability

Treat breaker state changes as **first-class events**. Emit `circuit_breaker_state_change` (or the project's equivalent) on every transition with at minimum:

```json
{
  "event": "circuit_breaker_state_change",
  "breaker": "resy",
  "from": "closed",
  "to": "open",
  "trigger": "consecutive_failures",
  "consecutive_failures": 5,
  "timestamp": "2026-05-24T18:32:17Z"
}
```

Pin two alert thresholds:

- **Page** when any breaker stays Open for > 5 minutes — at that point user impact is non-trivial.
- **Notify (chat channel)** on every Open transition — for trend visibility, even when it recovers in 60s.

`pybreaker` exposes listeners via `add_listener(MyListener())`; `opossum` emits `open` / `close` / `halfOpen` events. Wire both to the project's structured logger and metrics exporter so time-in-Open per breaker shows up on dashboards — that's the signal that distinguishes "a brief outage" from "a hard down."

### Anti-patterns

- **Breakers around in-process pure functions.** The breaker exists to model recovery on a remote dependency. A local function has no "recovering" state — handle the exception directly.
- **Breakers with no timeout on the wrapped call.** A hung call never returns, never increments the failure counter, and the breaker never opens. Always pair with a per-call timeout (`timeout=10.0`).
- **Single global breaker across multiple services.** Resy's outage blocks healthy OpenTable traffic. One breaker per dependency, always.
- **Resetting to Closed without a Half-Open probe.** Causes oscillation: failure → Open → time-elapses → Closed → failure → Open. The Half-Open single-probe model is what gives the dependency space to recover. Don't disable it.
- **Counting business 4xx as failures.** A `404 Not Found` on a lookup is application logic, not dependency health. Use `exclude=[httpx.HTTPStatusError]` (Python) or filter via `errorFilter` (opossum). Otherwise normal user behaviour can open the breaker.
- **Tripping on the first failure (`fail_max=1`).** Networks are flaky; a single 502 happens. Start at 5 and tune from real data.
- **Catching `CircuitBreakerError` and retrying.** Defeats the breaker. If you want to retry-on-recover, queue the work; don't busy-loop the breaker.

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
