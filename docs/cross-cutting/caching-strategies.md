# Cross-cutting: Caching strategies

**Concern:** Cache when you measurably need it, not when you imagine you do. Wrong cache invalidation is worse than no cache.
**Library:** Redis (`redis-py` / `ioredis`) for shared cache; in-process LRU (`functools.cache` / `lru-cache`) for hot per-process state.
**Lives in:** Inline below — applied per recipe based on measured need.

## What it provides

- A short list of when caching pays off and when it just adds bugs.
- The four canonical patterns (cache-aside / read-through / write-through / write-behind) with one-line tradeoffs.
- TTL guidance per data type, with jitter to defuse thundering-herd.
- Cache-stampede prevention via singleflight + early refresh.
- LLM response caching pattern (`sha256(model + prompt + params)`).
- Negative caching for "not found" results.

## When to cache

Cache layers add complexity, failure modes, and freshness debates. Justify each one with measured data:

- Repeated reads of the same data within a TTL window where freshness is acceptable.
- Expensive computations: LLM responses, embeddings, large joins, third-party API calls.
- Reducing third-party rate-limit pressure (cache responses; renew on TTL).
- Smoothing latency tails when a downstream is occasionally slow.

Don't cache:

- Per-request unique data (no second hit will ever read it).
- Highly time-sensitive data (real-time inventory; auction prices).
- Tiny payloads where the cache round-trip costs more than recomputation.
- Anything you can't invalidate or version cleanly.

## Patterns

### Cache-aside (default; most common)

The application reads the cache; on miss, fetches from source and writes the cache. The cache is allowed to be missing data the source has.

```python
async def get_customer(customer_id: str) -> Customer:
    key = f"customer:{customer_id}"
    cached = await cache.get(key)
    if cached:
        return Customer.model_validate_json(cached)
    customer = await db.get_customer(customer_id)
    await cache.set(key, customer.model_dump_json(), ex=300)
    return customer
```

```typescript
async function getCustomer(customerId: string): Promise<Customer> {
  const key = `customer:${customerId}`;
  const cached = await cache.get(key);
  if (cached) return Customer.parse(JSON.parse(cached));
  const customer = await db.getCustomer(customerId);
  await cache.set(key, JSON.stringify(customer), "EX", 300);
  return customer;
}
```

### Read-through

The cache itself loads on miss via a configured loader. Less common; requires a cache layer that supports it (some local caches, e.g. `cachetools.cached`, can be wired this way).

### Write-through

Every write goes to both the cache and the source synchronously. Cache always fresh; write latency is the sum of both backends.

### Write-behind (write-back)

Writes go to the cache first; flushed to the source asynchronously by a background worker. Fast writes; data loss risk if the cache crashes before the flush. Rarely the right choice for OLTP — useful for metrics-style aggregations.

### Refresh-ahead

A background worker re-fetches entries near expiry, so hot keys never actually go cold. Reduces miss latency on hot items; requires a background worker and a way to identify "hot."

## Cache invalidation

The hard problem. Three approaches, in increasing complexity:

| Approach | Tradeoff |
|----------|----------|
| **TTL only** | Simple; data stale up to TTL; safe; works for almost everything |
| **Event-based** | Fresh; needs reliable delivery (an event that doesn't reach the cache invalidator = silent staleness) |
| **Versioned keys** | Update by writing a new key (`customer:c-123:v2`); old key expires naturally; no explicit invalidation |

**Rule of thumb:** TTL covers 90% of cases. Reach for event-based invalidation only when stale-by-TTL latency is unacceptable for the use case. Reach for versioned keys when you want zero risk of serving an old value to a new schema.

## TTL design

Suggested starting points — tune to measured stale-ness tolerance.

| Data type | Suggested TTL |
|-----------|---------------|
| Static reference data (currencies, ISO countries) | 24 h |
| User profile / customer preferences | 5–15 min |
| Computed aggregations | 1–5 min |
| Restaurant availability snapshots | 30 s – 2 min |
| Real-time inventory | 5–30 s, or don't cache |
| LLM responses (deterministic prompts) | 1 h – 7 d |
| LLM embeddings (input-stable) | 30 d+ |
| Auth / authz decisions | 1–5 min, with explicit invalidation on role change |

### Always add jitter

A flat TTL on a hot key means thousands of callers all miss at the same instant and pile on the source — a cache stampede. Spread expiry uniformly:

```python
import random
ttl = 300 + random.randint(-30, 30)      # 270–330 s
await cache.set(key, value, ex=ttl)
```

## Cache stampede prevention

When a hot key expires (or never existed), all callers miss simultaneously and pile on the source. Two mitigations:

### Singleflight pattern

Only one in-flight load per key; everyone else waits.

```python
import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")

class Singleflight:
    def __init__(self) -> None:
        self._inflight: dict[str, asyncio.Future] = {}

    async def do(self, key: str, fn: Callable[[], Awaitable[T]]) -> T:
        if key in self._inflight:
            return await self._inflight[key]
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._inflight[key] = fut
        try:
            value = await fn()
            fut.set_result(value)
            return value
        except Exception as e:
            fut.set_exception(e)
            raise
        finally:
            del self._inflight[key]

sf = Singleflight()

async def get_with_singleflight(key: str, loader):
    cached = await cache.get(key)
    if cached:
        return cached
    return await sf.do(key, async_loader(loader, key))

async def async_loader(loader, key):
    val = await loader()
    await cache.set(key, val, ex=300)
    return val
```

### Early refresh

Refresh the cache *before* the TTL expires. If `now - written_at > 0.8 * ttl`, return the cached value AND kick off a background refresh. The hot key never actually expires from the perspective of the caller.

## Distributed cache (Redis)

For multi-instance services, in-process caches are inconsistent — different instances have different views. Use Redis as the shared cache layer (see `stack/cache-redis.md`).

### Key naming conventions

- `<service>:<entity>:<id>` — `rebooking:customer:c-123`
- `<service>:<entity>:<id>:<aspect>` — `rebooking:customer:c-123:preferences`
- Include the schema version when the cached shape changes — `rebooking:v2:customer:c-123`
- Use `:` as the separator throughout; never spaces or mixed delimiters.

### Serialization

| Format | Pros | Cons |
|--------|------|------|
| JSON | Human-readable; easy to debug from `redis-cli` | Verbose; slow for very large payloads |
| MessagePack | Compact; fast | Binary; needs a client library |
| Protobuf | Compact + schema'd | Heavy tooling |
| Pickle (Py) / `node:v8` serializer (TS) | Native objects | Cross-language pain; pickle is insecure on untrusted data |

Default to JSON unless you've measured the throughput / size limit. For LLM responses, JSON is fine — Redis is rarely the bottleneck.

## LLM response caching

Particularly valuable when:

- Prompts are deterministic (no random IDs, fresh timestamps, per-call entropy).
- The same prompt is likely to recur in a short window.
- The LLM call is expensive (Opus / extended thinking / large context).

Cache key = hash of `(model, prompt_text, parameters)`. TTL based on staleness tolerance for the answer.

```python
import hashlib
import json

def llm_cache_key(model: str, prompt: str, params: dict) -> str:
    blob = json.dumps(
        {"model": model, "prompt": prompt, "params": params},
        sort_keys=True,
    )
    return f"llm:{hashlib.sha256(blob.encode()).hexdigest()}"

async def cached_llm_call(model: str, prompt: str, params: dict) -> str:
    key = llm_cache_key(model, prompt, params)
    cached = await cache.get(key)
    if cached:
        return cached
    response = await call_llm(model, prompt, params)
    await cache.set(key, response, ex=3600)
    return response
```

The `agent-scaffold` CLI uses this same shape on the assembled-context block — see `agent-scaffold`'s prompt-caching pattern.

## Negative caching

"Not found" results deserve caching too. Without it, every lookup of a non-existent id hits the source on every request.

```python
NEG_SENTINEL = "__NULL__"

async def get_customer(customer_id: str) -> Customer | None:
    key = f"customer:{customer_id}"
    cached = await cache.get(key)
    if cached == NEG_SENTINEL:
        return None
    if cached:
        return Customer.model_validate_json(cached)
    customer = await db.get_customer(customer_id)
    if customer is None:
        await cache.set(key, NEG_SENTINEL, ex=60)   # short TTL for negatives
        return None
    await cache.set(key, customer.model_dump_json(), ex=300)
    return customer
```

Keep the negative TTL short (30–120 s) — the cache should adapt quickly when the data finally appears.

## Observability

- **Hit rate** per key prefix — `cache_hits_total{prefix=...}` / `cache_lookups_total{prefix=...}`.
- **Cold-cache effect after deploys** — saw-tooth pattern on source-load metrics.
- **TTL effectiveness** — what fraction of evictions are due to TTL vs LRU? LRU-dominated evictions mean undersized cache.
- **Singleflight wait time** — how often is the second caller waiting > 100 ms for the first to finish?

See `stack/prometheus-grafana.md` for the metrics surface.

## Pitfalls

- **Caching without an invalidation strategy** — stale data forever (or until restart).
- **Caching mutable data without versioning** — tearing across replicas; one instance has v1, another has v2.
- **Cache stampede** — flat TTLs on hot keys cause source-load spikes; jitter + singleflight.
- **In-process cache for a multi-instance service** — inconsistent reads. Move to Redis.
- **Caching PII without retention awareness** — orphan PII surviving deletion. Include the cache in your deletion fan-out (see `pii-gdpr.md`, PR-E pending).
- **Cache backed by a less-reliable service than the source** — cache outage = service outage. If you can't fall back to the source, you're using the cache as a DB.
- **Reading-from / writing-to cache without timeouts** — a stuck cache call hangs the request path.
- **Caching error responses by accident** — a transient 500 cached for 5 min becomes a 5-min outage.

## Where used in repo

- [stack/cache-redis.md](../stack/cache-redis.md) — Redis is the canonical shared cache layer.
- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — applicable to customer-preference lookups and restaurant-availability checks (future work; not yet wired).

## Production considerations

- **Cluster sizing** — `memory ≈ entry_size × hot_set_size + 30% headroom`. Monitor `used_memory` vs `maxmemory`.
- **`maxmemory-policy`** — `allkeys-lru` for cache workloads (Redis evicts cold entries automatically). `noeviction` for caches turns into "fails to write at capacity" which is rarely what you want.
- **Disaster posture** — cache loss should mean **degraded mode (slow)**, not outage. If a cache outage is an outage, you're using the cache as a DB — back off.
- **Multi-tenant caches** — prefix every key with `tenant_id`; never let two tenants share a key namespace.
- **Cost** — Redis memory is the lever; small entries cost almost nothing, large entries add up fast. Compress large values when sensible.

## See also

- `stack/cache-redis.md` — Redis as the cache layer.
- `validation-strategy.md` — cache validated objects, not raw payloads.
- `stack/prometheus-grafana.md` — instrument hit rate, eviction rate, latency.
- `pii-gdpr.md` (PR-E, pending) — include the cache in any deletion fan-out for PII.
