# Cross-cutting: Dead-letter queue operations

**Concern:** Treat the DLQ as an operational queue, not a graveyard. Every entry is human-triggered work; every replay is an audited action.
**Library:** Broker primitives (Redis Streams / Kafka topic / SQS DLQ) + project CLI + audit log
**Lives in:** Inline below — adopt per recipe; the consumer routes failures here, the CLI drives recovery.

## What it provides

- **Routing policy** — what belongs in the DLQ vs what should be retried or backpressured.
- **Self-contained message envelope** — every entry carries enough context to replay or drop without consulting the source system.
- **Retention + size budgets** — alert before the queue fills the broker.
- **A replay CLI** — list, inspect, replay (with dry-run + batch), drop. Always audited.
- **Alert thresholds + runbook** — page, notify, inform tiers tied to growth velocity and age.

## Why this exists

DLQs silently grow until something else breaks — disk fills, broker hits memory cap, or someone notices weeks later that no rebooking succeeded for a specific platform. The recipe writes events to `reservations.cancelled.dlq` when retries exhaust, then stops. Without ops guidance there's no answer to "what happens next."

The DLQ is the queue where every entry needs a person. Treat it that way: measurable, replayable, droppable with an audit trail.

## What goes to DLQ

| Goes to DLQ | Stays in source / handled elsewhere |
|-------------|-------------------------------------|
| Validation failures after `MAX_RETRIES` (schema fail, business rule violation) | Transient downstream errors (5xx, timeouts) — let [retry](resilience.md#retries) handle these |
| Poison messages (deserialization fails on first read) | Throttling responses (429) — use [backpressure](backpressure.md), not DLQ |
| Idempotency conflicts the consumer can't resolve (e.g., two different payloads for the same `idempotency_key`) | Open-circuit failures — route to slow lane / retry-later queue |
| Permanent business-rule failures (cancelled before the consumer ran, customer deleted, restaurant closed) | Unknown errors — keep retrying within `MAX_RETRIES` first; DLQ only when retries exhaust |

Rule of thumb: if a human needs to look at it before it can succeed, it belongs in the DLQ. If a retry might fix it, it doesn't.

## Message envelope

The DLQ entry must be **self-contained** — replaying or inspecting it must never require joining against the source stream (which may have aged out). Required fields:

```json
{
  "dlq_id": "01HVZ...",
  "original_event_id": "evt_01HVY...",
  "original_stream": "reservations.cancelled",
  "original_timestamp": "2026-05-24T14:32:11Z",
  "dlq_timestamp": "2026-05-24T14:34:47Z",
  "handler_name": "rebook_orchestrator",
  "handler_version": "1.4.2",
  "tenant_id": "rest_acme_123",
  "retry_count": 3,
  "failure_reason": "validation_failed",
  "last_error_class": "ReservationPlatformError",
  "last_error_message": "platform Resy: reservation not found (id=resy_42)",
  "replayed": false,
  "payload": { ... original event body ... }
}
```

`failure_reason` should be an enum your consumer chooses from (`validation_failed` / `poison_message` / `idempotency_conflict` / `business_rule_failed` / `unknown`). The free-text `last_error_message` is for the human; the enum is for routing and alerts.

`replayed: true` is set when the DLQ tool re-publishes — the consumer can drop or special-case replays to avoid loops.

## Retention

| Tier | Default | Why |
|------|---------|-----|
| Hot retention (queriable) | 30 days | Covers a full ops rotation; long enough to catch slow-burn issues |
| Cold archive | 1 year | For regulatory / audit. Store in object storage, not the broker. |
| Tenant-specific | Per contract | Some tenants require shorter retention for PII compliance — see [pii-gdpr.md](pii-gdpr.md) |

Track DLQ size as a primary metric: `dlq_depth{stream="..."}` + `dlq_growth_rate{stream="..."}`. Growth rate is the leading indicator; size is the lagging.

## Replay CLI

Every DLQ deserves a CLI. Conventions:

```bash
# List recent DLQ entries
agent-rebook dlq list [--since 24h] [--reason validation_failed] [--tenant rest_acme_123]

# Inspect one entry (full envelope, pretty-printed)
agent-rebook dlq inspect <dlq_id>

# Replay — preview first
agent-rebook dlq replay <dlq_id> --dry-run
agent-rebook dlq replay <dlq_id>                  # single entry
agent-rebook dlq replay --reason validation_failed --since 24h --batch 100

# Drop with a reason (always audited; reason required)
agent-rebook dlq drop <dlq_id> --reason "customer deleted account 2026-05-23"
agent-rebook dlq drop --reason "duplicate of evt_X" --since 24h --batch 50
```

Replay re-publishes to the source stream with `replayed: true` on the envelope. The handler checks `replayed` and either accepts (most cases) or routes to a separate replay-lane (when replays carry different retry semantics).

Drop is permanent within the hot retention window — cold archive still has it. Always require `--reason`; record `(operator, timestamp, reason, dlq_id, action)` to [audit-logging.md](audit-logging.md).

## Alert thresholds

| Tier | Trigger | Channel |
|------|---------|---------|
| **Page** | DLQ growth > 100/hour, OR any new `failure_reason`/`last_error_class` never seen before, OR depth > 1000 | On-call rotation |
| **Notify** | DLQ growth > 10/hour, OR depth > 100 | Team Slack channel |
| **Inform** | Any entry older than 7 days, OR weekly DLQ digest | Weekly ops email / dashboard tile |

Page on *velocity* and *novelty* rather than absolute depth — a steady-state depth of 50 from a known-tolerable cause shouldn't wake someone, but +100 in an hour means something just broke.

## Runbook outline

When a DLQ alert fires:

1. **Triage** — `dlq list --since 1h` and group by `failure_reason` + `last_error_class`. Common cluster?
2. **Root cause** — is the issue fixed? A known downstream that just recovered, a deploy that introduced the bug? `git log` + recent deploys + the broker's metrics tile.
3. **Dry-run replay** — `dlq replay --since 1h --dry-run` to confirm the entries would route correctly.
4. **Batched replay** — `dlq replay --since 1h --batch 100`. Watch consumer lag and the DLQ growth-rate metric for 5 minutes; if entries are landing back in the DLQ, **stop**, the underlying issue isn't fixed.
5. **Selective drop** — for entries that are non-replayable (expired bookings, deleted customers, duplicates), `dlq drop --reason "..."` with a clear reason for the audit log.
6. **Post-incident** — for any new `failure_reason` value, add a runbook entry under "known failure modes" so the next page is faster.

## Composition

- **With [observability.md](observability.md)** — DLQ depth + growth rate metrics, alerts on the tiers above, dashboard tile showing top 5 `failure_reason` over 24h.
- **With [audit-logging.md](audit-logging.md)** — every `replay` and `drop` is logged as `(operator, action, dlq_id, reason, timestamp)`. The DLQ CLI must refuse to run without an authenticated operator context.
- **With [multi-tenancy.md](multi-tenancy.md)** — per-tenant DLQ filtering (`--tenant`); tenant-managed services may need a self-service DLQ view scoped to their own entries. Never expose another tenant's `payload` (which may contain PII).
- **With [backpressure.md](backpressure.md)** — DLQ growth is itself a backpressure signal: if the rate of DLQing exceeds N/min, the consumer should slow ingress, not just keep producing more DLQ entries.
- **With [resilience.md](resilience.md)** — DLQ is the terminal state after retries + circuit-breaker fallbacks have exhausted. Configure `MAX_RETRIES` low (3) and let the DLQ catch the rest, rather than retrying for hours.

## Tests

- **DLQ-on-exhaust test** — force a permanent failure; assert the event lands on the DLQ stream after `MAX_RETRIES`, with all envelope fields populated.
- **Replay round-trip test** — write a known entry to DLQ; call `dlq replay`; assert the source stream receives it with `replayed: true` and the consumer processes it.
- **Drop audit test** — call `dlq drop`; assert the audit log contains `(operator, dlq_id, reason, timestamp)`.
- **Envelope-completeness test** — for each `failure_reason` enum value, assert the entry contains every required field (use a parametrized test against the enum).

## Pitfalls

- **Treating the DLQ as a graveyard** — entries accumulate forever, no one looks. Wire growth-rate alerts before the first DLQ event lands.
- **Envelope holds a reference, not the payload** — source stream ages out, replay becomes impossible. Always inline the full original payload.
- **Replay without `replayed: true`** — handler can't distinguish a replay from a fresh event; replay loops become possible.
- **Drop without a reason** — audit log has no signal for "why did this disappear?" months later. Make `--reason` required.
- **Per-handler DLQs without a common envelope** — five different DLQ shapes mean five different CLIs and zero shared dashboards. Standardise the envelope.
- **Auto-replay on schedule** — "the cron just retries the DLQ every hour" hides the underlying issue and amplifies bad-data incidents. Replay is a human-triggered action.
- **Counting all DLQ entries as failures equally** — a `business_rule_failed` (customer deleted account) is different from a `poison_message`. Tag and alert on the enum.

## Where used in repo

- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — `reservations.cancelled.dlq` Redis Stream; `MAX_RETRIES=3` before routing; admin HTTP endpoints `/admin/dlq` (list / inspect) and `/admin/replay` (replay); CLI subcommands wrap those endpoints for operator use.
