# Cross-cutting: Health checks and graceful shutdown

**Concern:** Three probes (startup, liveness, readiness) plus one shutdown sequence — get them right or rolling deploys cause user-visible incidents.
**Library:** FastAPI lifespan + stdlib `signal` (Py) / Hono + Node `process` (TS)
**Lives in:** Inline below — every long-running service wires this in its app lifespan.

## What it provides

- **Three orthogonal probes** -- startup ("done initializing?"), liveness ("still alive?"), readiness ("should I take traffic?"). Pointing all three at the same deep check is a load-bearing footgun.
- **Drain sequence on SIGTERM** -- stop taking new work, finish in-flight work, close clients in dependency order, exit cleanly.
- **Consumer-loop shutdown** -- event-driven workers respect the same shutdown signal; a loop that ignores SIGTERM holds messages until the orchestrator force-kills it.

## Why this exists

Kubernetes, ECS, Nomad, Fly — all of them assume the process distinguishes "starting" from "alive" from "ready" and reacts to SIGTERM correctly. When the app conflates them:

- A slow downstream causes the orchestrator to restart the pod (liveness flap), making the outage worse.
- A new rollout starts serving traffic before migrations finish (no startup probe), and the first 30 seconds are 500s.
- A rolling deploy drops in-flight requests because the pod exits before the load balancer notices it's gone (no prestop delay).
- An event consumer holds claims forever because the loop never sees SIGTERM (no signal handler), and redelivery is blocked until the claim TTL expires.

Each of these is a one-line fix if you know the pattern. They're standard interview-question gotchas because they bite every team at least once.

## Three probes (Kubernetes conventions; usable anywhere)

| Probe | Purpose | What to check | Failure action |
|-------|---------|---------------|----------------|
| **Startup** | "Have I finished initializing?" | Migrations applied, caches warm, consumer subscribed, model weights loaded | Restart after grace period |
| **Liveness** | "Am I alive?" (cheap, local) | Event loop responsive; no deadlock | Kill + restart |
| **Readiness** | "Should I receive traffic?" | All deps reachable, not draining, consumer lag healthy | Remove from load balancer |

### The anti-pattern to avoid

Pointing all three probes at the same deep healthcheck. When the database blips:

- Readiness fails → load balancer removes you. ✅ Correct.
- Liveness fails → orchestrator restarts you. ❌ Wrong — restarting won't fix a DB problem, and now you've added cold-start latency on top of the outage.
- Startup fails → orchestrator restarts you again. ❌ Same problem.

**Liveness must be cheap and local** — `return {"status": "ok"}` is often enough. The signal to escalate is "this process has wedged," not "a dependency is sick."

## Implementation patterns

### FastAPI example

```python
from fastapi import FastAPI, HTTPException, APIRouter

app = FastAPI()
router = APIRouter()

@router.get("/health/live")
async def live() -> dict:
    # Cheap, local. Just proves the event loop is turning.
    return {"status": "ok"}

@router.get("/health/startup")
async def startup() -> dict:
    if not app.state.ready:
        raise HTTPException(503, detail="initializing")
    return {"status": "ok"}

@router.get("/health/ready")
async def ready() -> dict:
    if app.state.shutting_down:
        raise HTTPException(503, detail="draining")
    checks = {
        "redis":   await ping_redis(app.state.redis),
        "postgres": await ping_postgres(app.state.pg),
    }
    if not all(checks.values()):
        raise HTTPException(503, detail=checks)
    return {"status": "ok", **checks}

app.include_router(router)
```

### Hono example

```typescript
import { Hono } from "hono";

const app = new Hono();
const state = { ready: false, shuttingDown: false };

app.get("/health/live", (c) => c.json({ status: "ok" }));

app.get("/health/startup", (c) =>
  state.ready ? c.json({ status: "ok" }) : c.json({ status: "initializing" }, 503),
);

app.get("/health/ready", async (c) => {
  if (state.shuttingDown) return c.json({ status: "draining" }, 503);
  const checks = {
    redis: await pingRedis(),
    postgres: await pingPostgres(),
  };
  return Object.values(checks).every(Boolean)
    ? c.json({ status: "ok", ...checks })
    : c.json({ status: "degraded", ...checks }, 503);
});
```

### Event-consumer ready check

For services whose primary job is consuming events (Redis Streams, Kafka, SQS), readiness should also include progress evidence — a consumer that's wedged with no error is unhealthy:

```python
@router.get("/health/ready")
async def ready() -> dict:
    lag = await get_consumer_lag()       # XPENDING length, or Kafka committed-lag
    last_processed_age = time.time() - app.state.last_processed_ts
    if lag > MAX_HEALTHY_LAG:
        raise HTTPException(503, detail={"lag": lag})
    if last_processed_age > STALL_THRESHOLD_SECONDS and lag > 0:
        raise HTTPException(503, detail={"stalled_seconds": last_processed_age})
    return {"status": "ok", "lag": lag}
```

`MAX_HEALTHY_LAG` depends on throughput — pick something well above steady-state lag but well below "consumer is dead."

## Graceful shutdown sequence

The orchestrator sends SIGTERM, waits `terminationGracePeriodSeconds` (default 30s in Kubernetes), then SIGKILL. Your job is to exit cleanly before the SIGKILL.

```
1. SIGTERM received
   └─ set shutting_down = True
       └─ readiness probe starts returning 503
2. Sleep PRESTOP_DELAY seconds (10–30s)
   └─ load balancer notices, stops sending new traffic
3. Stop accepting new work
   └─ close HTTP server to new connections
   └─ stop XREADGROUP / poll() on event consumer
4. Drain in-flight work
   └─ await all handlers, up to SHUTDOWN_TIMEOUT
5. Close clients in dependency order
   └─ HTTP clients → Redis → Postgres pool
6. Exit 0
```

`PRESTOP_DELAY` is the part most people miss. The load balancer learns about your removal asynchronously (probe interval, propagation lag). Without the delay, you close the HTTP server while the LB is still routing traffic to you — those connections are dropped mid-request.

### Python lifespan example

```python
import asyncio
import signal
from contextlib import asynccontextmanager
from fastapi import FastAPI

PRESTOP_DELAY = 15
SHUTDOWN_TIMEOUT = 30

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- startup ----
    app.state.redis = await redis.from_url(REDIS_URL)
    app.state.pg = await asyncpg.create_pool(PG_URL)
    app.state.shutting_down = False
    app.state.ready = False

    consumer_task = asyncio.create_task(consumer_loop(app))
    app.state.ready = True

    yield

    # ---- shutdown ----
    app.state.shutting_down = True
    await asyncio.sleep(PRESTOP_DELAY)  # let LB notice readiness flip

    consumer_task.cancel()
    try:
        await asyncio.wait_for(consumer_task, timeout=SHUTDOWN_TIMEOUT)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass

    await app.state.pg.close()
    await app.state.redis.close()


app = FastAPI(lifespan=lifespan)


async def consumer_loop(app: FastAPI) -> None:
    while not app.state.shutting_down:
        msgs = await app.state.redis.xreadgroup(
            "workers", "w1", {"events": ">"}, count=10, block=1000,
        )
        for stream, entries in msgs:
            for msg_id, payload in entries:
                await handle(payload)
                await app.state.redis.xack("events", "workers", msg_id)
```

Two important details:

- **The consumer loop checks `shutting_down` between iterations**, not just at start. The `block=1000` means the loop wakes at least every second to re-check.
- **Don't ACK before the work completes.** ACK on success only; redelivery handles crashes mid-handler (see [idempotency.md](idempotency.md)).

### Node example

```typescript
import { serve } from "@hono/node-server";

const state = { ready: false, shuttingDown: false };
const PRESTOP_DELAY_MS = 15_000;
const SHUTDOWN_TIMEOUT_MS = 30_000;

const server = serve({ fetch: app.fetch, port: 8080 });
state.ready = true;

async function shutdown(): Promise<void> {
  state.shuttingDown = true;
  await new Promise((r) => setTimeout(r, PRESTOP_DELAY_MS));

  server.close();
  await stopConsumer(); // sets a flag the consumer loop checks

  await Promise.race([
    drainInFlight(),
    new Promise((r) => setTimeout(r, SHUTDOWN_TIMEOUT_MS)),
  ]);

  await pgPool.end();
  await redis.quit();
  process.exit(0);
}

process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
```

## Kubernetes probe config (reference)

```yaml
startupProbe:
  httpGet: { path: /health/startup, port: 8080 }
  failureThreshold: 30        # 30 × 5s = 150s to start
  periodSeconds: 5
livenessProbe:
  httpGet: { path: /health/live, port: 8080 }
  periodSeconds: 10
  failureThreshold: 3
readinessProbe:
  httpGet: { path: /health/ready, port: 8080 }
  periodSeconds: 5
  failureThreshold: 2
lifecycle:
  preStop:
    exec: { command: ["sh", "-c", "sleep 15"] }   # belt + suspenders for PRESTOP_DELAY
terminationGracePeriodSeconds: 60                 # > PRESTOP_DELAY + SHUTDOWN_TIMEOUT
```

The `preStop` hook duplicates what the app's own shutdown sequence does for `PRESTOP_DELAY`. Either is fine; having both is harmless and robust to deploys of older app versions.

## Tests

- **Probe behavior test** -- assert `/health/live` is always 200; `/health/ready` flips to 503 when `shutting_down = True`; `/health/startup` flips to 200 only after init completes.
- **Drain test** -- send SIGTERM mid-request; assert in-flight request completes and process exits 0 within `SHUTDOWN_TIMEOUT`.
- **Consumer-loop test** -- assert the loop exits within one iteration of `shutting_down = True` being set.

## Pitfalls

- **No prestop delay** -- in-flight requests dropped during load balancer removal.
- **Liveness too deep** -- a slow downstream causes pod restarts instead of just stopping traffic.
- **No timeout on drain** -- a stuck handler hangs the deploy forever.
- **`terminationGracePeriodSeconds < PRESTOP_DELAY + SHUTDOWN_TIMEOUT`** -- SIGKILL hits before drain finishes.
- **Forgetting to close DB pools** -- connection leak shows up as "too many connections" on the DB side after enough rollouts.
- **Consumer loop without signal awareness** -- holds claims until TTL, blocks redelivery.
- **ACK before work succeeds** -- crash mid-handler loses the message. Always ACK after.

## Where used in repo

- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — `/health/live`, `/health/ready`, `/health/startup` on the admin HTTP layer; consumer loop respects `shutting_down`; drain sequence wired into the FastAPI lifespan.
