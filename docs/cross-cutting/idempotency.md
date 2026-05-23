# Cross-cutting: Idempotency

**Concern:** Make every action-taking operation safe to retry by keying it on a stable idempotency key.
**Library:** Redis `SET ... NX EX` (Py / TS) + DB unique constraints
**Lives in:** Inline below — adopt per recipe; no shared module yet.

## What it provides

- **Two-phase claim/release** -- protects event handlers against at-least-once redelivery without silently dropping crashed-mid-work events.
- **Single-phase SETNX** -- cheap dedupe for already-idempotent writes (UPSERTs, INSERT ... ON CONFLICT).
- **Unique-constraint dedup** -- the database does the dedupe when the idempotency key is stored alongside the row.
- **Outbound idempotency keys** -- pass `Idempotency-Key` to third-party APIs (Stripe, Twilio, SendGrid) so retries on your side don't duplicate downstream.

## Why this exists

At-least-once delivery is the default for every event source worth running in production (Redis Streams `XREADGROUP`, Kafka consumer groups, SQS, SNS, Pub/Sub). HTTP retries -- whether from clients, load balancers, or your own `tenacity` wrapper -- have the same shape. The only way to reach end-to-end "exactly-once" semantics is to make the action itself idempotent, then let the transport layer redeliver freely.

If you skip this, expect: duplicate notifications, double-charged payments, two reservations for the same slot, eval datasets polluted by replayed events.

## Where to apply it

- Event handlers consuming from Redis Streams, Kafka, SQS, Pub/Sub
- HTTP `POST`/`PUT`/`DELETE` endpoints that mutate state
- Outbound calls to third-party APIs that charge or notify
- Job-queue handlers (Celery, BullMQ, RQ)
- Webhook receivers (every webhook provider retries)

## Idempotency key design

Three things matter — source, scope, TTL.

**Source of the key**, in order of preference:

1. **Producer-assigned UUID** -- the event/message carries the key. Same event id ⇒ same key ⇒ obvious dedupe.
2. **Content hash** -- `sha256(canonical_json(payload))`. Useful when the producer can't be trusted to assign one, but watch for legitimate retries that intentionally differ by timestamp.
3. **Server-assigned** -- last resort. Only works when the client cooperates by echoing the key on retry.

**Scope** -- prefix the key with the operation namespace so you don't collide:

- `notify:{customer_id}:{event_id}` -- per-customer per-event notification
- `rebook:{event_id}` -- one rebooking attempt per source event
- `webhook:stripe:{event[id]}` -- per-provider per-event id

**TTL** -- must exceed the upstream's max redelivery window plus your own retry budget. Redis Streams `MAXLEN` retention, Kafka `retention.ms`, SQS `MessageRetentionPeriod` are the lower bound. Set TTL to `2 × max_retention` so a delayed redelivery still hits the cache.

## Patterns

### Two-phase idempotency (recommended for event handlers)

Use this when the work might fail or crash mid-way. Single-phase SETNX silently drops events whose worker crashed after `SETNX` but before completing the work.

```python
import redis.asyncio as redis

CLAIM_TTL_SECONDS = 60        # how long a worker is allowed to hold the claim
FINAL_TTL_SECONDS = 24 * 3600 # how long to remember "done" (must exceed redelivery window)

async def handle_event(client: redis.Redis, event_id: str, payload: dict) -> None:
    key = f"idemp:rebook:{event_id}"

    # Claim phase
    claimed = await client.set(key, "claimed", ex=CLAIM_TTL_SECONDS, nx=True)
    if not claimed:
        status = await client.get(key)
        if status == b"completed":
            return  # already processed — safe to ACK
        return      # another worker is mid-flight — don't double-process; do not ACK

    # Work phase
    try:
        await do_work(payload)
        await client.set(key, "completed", ex=FINAL_TTL_SECONDS)
    except Exception:
        await client.delete(key)  # release the claim so the retry can re-claim
        raise
```

```typescript
import Redis from "ioredis";

const CLAIM_TTL_SECONDS = 60;
const FINAL_TTL_SECONDS = 24 * 3600;

export async function handleEvent(
  client: Redis,
  eventId: string,
  payload: unknown,
): Promise<void> {
  const key = `idemp:rebook:${eventId}`;

  const claimed = await client.set(key, "claimed", "EX", CLAIM_TTL_SECONDS, "NX");
  if (!claimed) {
    const status = await client.get(key);
    if (status === "completed") return; // already processed
    return;                              // another worker holds the claim
  }

  try {
    await doWork(payload);
    await client.set(key, "completed", "EX", FINAL_TTL_SECONDS);
  } catch (err) {
    await client.del(key); // release claim for retry
    throw err;
  }
}
```

**Tradeoff vs single-phase SETNX:** the claim-then-complete dance costs an extra Redis round-trip and a small window where a crashed worker blocks retries until `CLAIM_TTL_SECONDS` expires. In return, you never silently dedupe an event whose worker crashed before doing the work.

### Single-phase SETNX (acceptable for write-then-read paths)

When the work is itself idempotent — a SQL `UPSERT` on a unique constraint, or a `PUT` to an object store — the claim/release dance is overkill. Just use `SETNX` as a fast-path dedupe:

```python
async def handle_event_fast(client: redis.Redis, event_id: str, payload: dict) -> None:
    key = f"idemp:{event_id}"
    if not await client.set(key, "1", ex=FINAL_TTL_SECONDS, nx=True):
        return  # dupe
    await upsert_row(payload)  # itself idempotent
```

If `upsert_row` fails, the next redelivery re-hits the SETNX, finds it set, and silently drops — which is fine because the work is idempotent and a future redelivery within TTL is a no-op anyway. Use this when you can prove the inner work is safe to drop on a single failure path.

### Unique-constraint dedup

The most robust pattern when the action writes a row. Store the idempotency key as a column with a unique constraint and let the database do the dedupe:

```sql
CREATE TABLE notifications (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL,
    event_id    TEXT NOT NULL,
    sent_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (customer_id, event_id)
);
```

```python
try:
    await conn.execute(
        "INSERT INTO notifications (customer_id, event_id) VALUES ($1, $2)",
        customer_id, event_id,
    )
    await send_email(...)
except UniqueViolationError:
    return  # already sent
```

Pair this with the actual side effect inside a transaction so a successful row insert and a failed email both roll back together — or accept the at-least-once shape and tolerate occasional duplicate sends.

### Outbound idempotency keys

Many third-party APIs accept an `Idempotency-Key` header. **Always** pass one — never assume the upstream service dedupes on its own:

```python
async def send_payment(stripe_client, charge_id: str, ...):
    return await stripe_client.charges.create(
        amount=...,
        idempotency_key=f"charge:{charge_id}",  # Stripe stores results for 24h keyed on this
    )
```

Stripe, Twilio, SendGrid, Square, Adyen, and most payment/notification APIs support this. The key should be your internal stable id for the action, not a random per-call value.

## Tests

- **Replay test** -- emit the same event twice; assert exactly one side-effect (one row inserted, one outbound API call observed via mock).
- **Crash-recovery test** -- inject failure between claim and completion; assert the next redelivery re-claims and completes (two-phase) or assert the action is replay-safe (single-phase).
- **TTL-expiry test** -- after `FINAL_TTL_SECONDS + 1`, a replay must be re-processed (or the TTL is misconfigured).

## Pitfalls

- **TTL shorter than the redelivery window** -- duplicates slip through after the key expires.
- **Forgetting to release the claim on failure** -- stale claims block retries until `CLAIM_TTL_SECONDS`. Always `delete` in the `except`.
- **Key scope too coarse** -- `idemp:{event_id}` collides if two unrelated handlers process the same event id. Prefix the operation: `idemp:rebook:{event_id}`.
- **Mixing key namespaces** -- using `event_id` as both the claim key and the row primary key forces both schemas to agree forever. Keep them separate.
- **Per-request idempotency for `GET`** -- `GET` is already safe; adding an idempotency layer is wasted complexity.
- **Trusting downstream dedupe** -- "Stripe dedupes for us" is true only when you pass `Idempotency-Key`. The default is at-least-once on your side.

## Where used in repo

- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — two-phase claim/release in the Redis Streams consumer loop; unique-constraint dedup on the `outcomes` table.
