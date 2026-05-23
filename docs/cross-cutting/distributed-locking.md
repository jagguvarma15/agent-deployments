# Cross-cutting: Distributed locking

**Concern:** Mutual exclusion across multiple instances of a service — used sparingly, because the right answer is usually idempotency.
**Library:** Redis `SET ... NX EX` + Lua release (Py / TS) / Postgres `pg_try_advisory_lock`
**Lives in:** Inline below — reach for it only when single-leader semantics are genuinely required.

## What it provides

- **Single-instance Redis lock** with token + Lua release — correct under TTL expiry races.
- **Postgres advisory lock** — simpler semantics for workloads already on Postgres; auto-released on session end.
- **Pointer to Redlock** — multi-instance Redis lock; included for completeness, almost always overkill.

## Why this exists — and why you usually don't want it

Distributed locks are the wrong answer to most "make this run once" problems. They:

- Add latency (acquire/release round-trips on the hot path).
- Add failure modes (process crashes with lock held, TTL expires mid-work, network partition fakes a release).
- Hide the actual requirement, which is usually "this side-effect should happen at most once" — which is what idempotency solves, without the locking complexity.

**Default to idempotency.** Reach for locking only when you genuinely need single-leader semantics — and most of the time you don't.

## When you actually need it

- **Single-leader scheduled jobs** — a nightly batch that must run once across N pods, not once per pod. (Or use the orchestrator's own primitives: Kubernetes `CronJob`, AWS EventBridge.)
- **Critical sections that genuinely cannot be made idempotent** — rare; push back hard before believing this.
- **Migration / backfill scripts** that must not run concurrently because they read-then-write without a usable unique constraint.
- **Leader election for cache warming / heartbeat publishing** — one writer, many readers.

## When you don't (and what to use instead)

| Anti-pattern | Use instead |
|--------------|-------------|
| "Lock the event handler so we don't double-process" | [Idempotency](idempotency.md) — two-phase claim or SETNX dedupe |
| "Lock the row so two updates don't clobber each other" | Database transaction + `SELECT FOR UPDATE`, or optimistic locking with a `version` column |
| "Lock the user record while we update profile" | Optimistic concurrency (`UPDATE ... WHERE version = ?`) |
| "Lock so we don't insert a duplicate" | Unique constraint on the row |
| "Just to be safe" | Nothing. Resist the urge. |

If the answer to "what goes wrong if two workers run this at once?" is "duplicate writes," idempotency is the fix. If it's "split-brain leader," then yes, you need a lock.

## Redis-based lock (single-instance)

The minimum-viable correct implementation. SET with `NX` + `EX` atomically claims; a Lua script releases only if the token matches.

```python
import asyncio
import uuid
from contextlib import asynccontextmanager
import redis.asyncio as redis

RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""

async def acquire_lock(client: redis.Redis, key: str, ttl_seconds: int = 30) -> str | None:
    token = str(uuid.uuid4())
    ok = await client.set(f"lock:{key}", token, ex=ttl_seconds, nx=True)
    return token if ok else None

async def release_lock(client: redis.Redis, key: str, token: str) -> bool:
    deleted = await client.eval(RELEASE_LUA, 1, f"lock:{key}", token)
    return bool(deleted)

@asynccontextmanager
async def lock(client: redis.Redis, key: str, ttl_seconds: int = 30):
    token = await acquire_lock(client, key, ttl_seconds)
    if not token:
        raise LockUnavailable(key)
    try:
        yield
    finally:
        await release_lock(client, key, token)

class LockUnavailable(Exception):
    pass


# Usage
async def nightly_cleanup(client: redis.Redis) -> None:
    try:
        async with lock(client, "cleanup:nightly", ttl_seconds=300):
            await run_cleanup()
    except LockUnavailable:
        return  # another pod is doing it
```

```typescript
import Redis from "ioredis";
import { randomUUID } from "node:crypto";

const RELEASE_LUA = `
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
`;

export async function withLock<T>(
  client: Redis,
  key: string,
  ttlSeconds: number,
  fn: () => Promise<T>,
): Promise<T | null> {
  const token = randomUUID();
  const ok = await client.set(`lock:${key}`, token, "EX", ttlSeconds, "NX");
  if (!ok) return null;
  try {
    return await fn();
  } finally {
    await client.eval(RELEASE_LUA, 1, `lock:${key}`, token);
  }
}
```

### Critical: token + Lua release

Releasing without a token check can delete a lock that a different worker acquired after your TTL expired. The race:

1. Worker A acquires `lock:cleanup` with TTL 30s.
2. Worker A's work hangs (slow downstream).
3. TTL expires — Redis deletes the key.
4. Worker B acquires `lock:cleanup` and starts working.
5. Worker A finishes, calls `DEL lock:cleanup` — releases B's lock.
6. Worker C acquires the now-free lock — two leaders.

The Lua script is atomic and only deletes when the token matches. **Never** call `DEL` directly to release.

### Even more critical: TTL > work duration

If your TTL is 30s but the work takes 45s, another worker will acquire the lock after 30s and you'll have two leaders for 15s. Two options:

- **Pick TTL > p99 of work duration + buffer**, e.g. `5 × p99`. Simple, works when work duration is bounded.
- **Lock refresh (heartbeat)** — a background task that extends the TTL while the work runs. Adds complexity and a new failure mode (heartbeat task crashes, real worker keeps running, TTL expires). Use only when work duration is unbounded.

```python
async def heartbeat(client: redis.Redis, key: str, token: str, ttl: int, interval: int):
    extend_lua = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('expire', KEYS[1], ARGV[2])
    end
    return 0
    """
    while True:
        await asyncio.sleep(interval)
        ok = await client.eval(extend_lua, 1, f"lock:{key}", token, ttl)
        if not ok:
            return  # lock was lost — caller should stop work
```

## Postgres advisory locks

For workloads already using Postgres, advisory locks are simpler than Redis and have well-defined semantics: released automatically when the session ends or transaction commits/rolls back. Good fit for migration / backfill scripts.

```python
async def with_advisory_lock(conn, lock_id: int):
    got = await conn.fetchval("SELECT pg_try_advisory_lock($1)", lock_id)
    if not got:
        return False
    try:
        # do work
        ...
    finally:
        await conn.execute("SELECT pg_advisory_unlock($1)", lock_id)
    return True
```

`pg_try_advisory_lock` is non-blocking — returns `false` immediately if another session holds it. Use `pg_advisory_lock` only when you actually want to queue. Lock id is an arbitrary `bigint`; namespace it with `hashtext('cleanup:nightly')::int` or similar.

Transaction-scoped variant: `pg_try_advisory_xact_lock(id)` releases on `COMMIT`/`ROLLBACK` with no explicit unlock needed.

## Redlock (multi-instance Redis)

For correctness across a Redis HA cluster, the Redlock algorithm (`pyredlock`, `redlock-py`) acquires the lock on a majority of independent Redis instances.

**Don't use this unless you understand the controversy.** Martin Kleppmann's critique points out that Redlock relies on clock-bound assumptions that don't hold under GC pauses, network partitions, or VM migrations. For most workloads, a single Redis instance with a short TTL + idempotent work is correct and dramatically simpler.

If you genuinely need correctness under Redis failover, the canonical answer is "use a CP system designed for this" — etcd, ZooKeeper, Consul — not Redlock.

## Tests

- **Mutual exclusion test** -- launch N concurrent `acquire_lock` calls; assert exactly one returns a token, the rest return `None`.
- **Release safety test** -- acquire, let TTL expire, acquire from another worker, attempt to release with the first token; assert the second worker still holds the lock.
- **TTL-expiry test** -- acquire with TTL 1s, wait 2s, attempt acquire from another worker; assert success.
- **Lua atomicity test** -- the release script returns 1 only when the token matches.

## Pitfalls

- **No TTL** -- process crashes, lock held forever, system wedged.
- **Releasing without token check** -- release someone else's lock; two leaders.
- **Locks held across slow I/O** -- blast radius of any slow downstream is multiplied by the lock duration.
- **Using a lock when idempotency would suffice** -- unnecessary complexity, latency, failure modes.
- **TTL shorter than work duration** -- two leaders.
- **Treating Redlock as a primitive you can use without thinking** -- it's not; pick a CP system if you need correctness under partition.

## Where used in repo

None yet — every event-driven flow in this repo uses [idempotency](idempotency.md). Reach for locking only when you genuinely need single-leader semantics.
