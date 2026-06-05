---
status: Blueprint (design spec)
languages: [python, typescript]
required_files:
  - Dockerfile
  - docker-compose.yml
  - .github/workflows/ci.yml
  - tests/unit/test_orchestrator.py
  - tests/integration/test_event_loop.py
  - tests/eval/test_rebooking_decisions.py
recipe_dependencies:
  python:
    redis: ">=5.0.0"
    sqlalchemy: ">=2.0.0"
    asyncpg: ">=0.29.0"
    alembic: ">=1.13.0"
    pydantic-settings: ">=2.0.0"
    fastapi: ">=0.110.0"
    uvicorn: ">=0.30.0"
    structlog: ">=24.1.0"
    langfuse: ">=2.0.0"
    prometheus-client: ">=0.20.0"
    pyjwt: ">=2.8.0"
    httpx: ">=0.27.0"
    pytest-asyncio: ">=0.23.0"
  typescript:
    ioredis: "^5.4.0"
    drizzle-orm: "^0.36.0"
    postgres: "^3.4.0"
    hono: "^4.0.0"
    pino: "^9.0.0"
    langfuse: "^3.0.0"
    zod: "^3.23.0"
    jose: "^5.0.0"
    vitest: "^2.0.0"
external_services:
  - postgres
  - redis
  - qdrant
  - langfuse
  - grafana
capabilities:
  - cache.redis
  - relational.postgres
  - vector_db.qdrant
  - queue.redis-streams
  - obs.langfuse
  - obs.grafana-stack
  - frontend.nextjs-chat
  - host.vercel
  - eval.promptfoo
bootstrap_config:
  vector_collections:
    - { name: docs, vector_size: 1536, distance: cosine }
  redis_streams:
    - { name: reservations.cancelled, maxlen: 10000, consumer_group: rebooker }
    - { name: reservations.rebooked, maxlen: 10000 }
    - { name: reservations.cancelled.dlq, maxlen: 10000 }
topology: multi-agent-flat
roles:
  - name: intake
    description: "Consume reservation-change events from Redis Streams, classify (cancel / no-show / modify), build the case envelope."
    model_hint: sonnet
    tools: [event_bus_consumer]
  - name: eligibility
    description: "Apply auto-rebook policy rules (tier, time window, customer history) to decide whether to attempt rebooking."
    model_hint: sonnet
    tools: [policy_lookup, customer_lookup]
  - name: search
    description: "Query alternative slots across reservation platforms (Resy, OpenTable, Toast) and rank candidates."
    model_hint: opus
    tools: [resy_adapter, opentable_adapter, toast_adapter]
  - name: notifier
    description: "Compose and send rebooking offers via email/SMS; record customer acceptance back to the case."
    model_hint: haiku
    tools: [email_send, sms_send]
load_list:
  - {path: ../patterns/event-driven.md, required: true}
  - {path: ../patterns/multi-agent-flat.md, required: true}
  - {path: ../frameworks/langgraph.md, required: true, when: "language == 'python'"}
  - {path: ../frameworks/mastra.md, required: true, when: "language == 'typescript'"}
  - {path: ../cross-cutting/project-layout.md, required: true}
  - {path: ../stack/llm-claude.md, required: true}
  - {path: ../stack/api-fastapi.md, required: false, when: "language == 'python'"}
  - {path: ../stack/api-hono.md, required: false, when: "language == 'typescript'"}
  - {path: ../stack/relational-postgres.md, required: false, when: "capabilities contains 'relational.postgres'"}
  - {path: ../stack/cache-redis.md, required: false, when: "capabilities contains 'cache.redis'"}
  - {path: ../stack/tracing-langfuse.md, required: false, when: "capabilities contains 'obs.langfuse'"}
  - {path: ../stack/secrets-management.md, required: true}
  - {path: ../cross-cutting/idempotency.md, required: true}
  - {path: ../cross-cutting/resilience.md, required: true}
  - {path: ../cross-cutting/backpressure.md, required: true}
  - {path: ../cross-cutting/dlq-operations.md, required: true}
  - {path: ../cross-cutting/logging-structured.md, required: false}
  - {path: ../cross-cutting/observability.md, required: false}
  - {path: ../cross-cutting/testing-strategy.md, required: false}
  - {path: ../cross-cutting/multi-tenancy.md, required: false}
  - {path: ../cross-cutting/cost-tracking.md, required: false}
  - {path: ../cross-cutting/model-routing.md, required: false}
  - {path: ../cross-cutting/health-graceful-shutdown.md, required: false}
  - {path: ../cross-cutting/security-hardening.md, required: false}
  - {path: ../cross-cutting/authorization-rbac.md, required: false}
  - {path: ../cross-cutting/audit-logging.md, required: false}
  - {path: ../cross-cutting/pii-gdpr.md, required: false}
---

# Recipe: Restaurant Rebooking

**Status:** Blueprint (design spec)

## Composes

- Pattern: [Event-Driven Agents](../patterns/event-driven.md) + [Multi-Agent Flat](../patterns/multi-agent-flat.md)
- Framework (Py): [LangGraph](../frameworks/langgraph.md) (explicit state machine fits event-driven lifecycle)
- Framework (TS): [Mastra](../frameworks/mastra.md) (event-triggered workflows)
- Stack: [FastAPI](../stack/api-fastapi.md) / [Hono](../stack/api-hono.md) (admin + health endpoints), [Redis](../stack/cache-redis.md) (event stream + idempotency), [Postgres](../stack/relational-postgres.md) (outcomes + state), [Langfuse](../stack/tracing-langfuse.md), [Secrets management](../stack/secrets-management.md) (Resy / OpenTable / Toast credentials)
- Cross-cutting: [Logging](../cross-cutting/logging-structured.md), [Observability](../cross-cutting/observability.md), [Testing strategy](../cross-cutting/testing-strategy.md), [Multi-tenancy](../cross-cutting/multi-tenancy.md), [Cost tracking](../cross-cutting/cost-tracking.md) (per-tenant per-day USD budget guards the LLM call; graceful-degrade Opus → Sonnet → Haiku above 80% of budget; paid-tool spend tracked alongside tokens), [Model routing](../cross-cutting/model-routing.md) (per-role `model_hint` already set on intake/eligibility/search/notifier; fallback chains on 429 / 5xx / budget-degrade; deterministic A/B randomization seeded by `(tenant_id, request_id)`), [Idempotency](../cross-cutting/idempotency.md), [Resilience](../cross-cutting/resilience.md) (one [circuit breaker](../cross-cutting/resilience.md#circuit-breakers) per reservation platform — Resy / OpenTable / Toast — so one platform's outage doesn't starve the others), [Backpressure](../cross-cutting/backpressure.md) (bounded `XADD MAXLEN` + semaphore concurrency cap + slow-lane shedding when a platform breaker opens), [DLQ operations](../cross-cutting/dlq-operations.md) (self-contained envelope on `reservations.cancelled.dlq`, replay CLI behind `/admin/replay`, paged on growth-rate not depth), [Health & graceful shutdown](../cross-cutting/health-graceful-shutdown.md), [Security hardening](../cross-cutting/security-hardening.md), [Authorization & RBAC](../cross-cutting/authorization-rbac.md), [Audit logging](../cross-cutting/audit-logging.md), [PII handling](../cross-cutting/pii-gdpr.md)

> **Auth/rate limiting:** the event-driven entry point doesn't need user auth (events come from trusted producers), but the admin/health HTTP layer does — see [auth-jwt.md](../cross-cutting/auth-jwt.md).

### Load list

Feed these files to your AI coding assistant to build this agent:

**Core (always load):**
- `docs/recipes/restaurant-rebooking.md` — this blueprint
- `docs/patterns/event-driven.md` — the event-driven agent pattern
- `docs/patterns/multi-agent-flat.md` — the multi-agent flat composition
- `docs/frameworks/langgraph.md` (Python) or `docs/frameworks/mastra.md` (TypeScript)
- `docs/stack/llm-claude.md` — LLM integration and model selection

**Stack (load for Tier 2 — event-driven runtime):**
- `docs/stack/cache-redis.md` — Redis Streams as the event source + idempotency store
- `docs/stack/relational-postgres.md` — outcome persistence + audit log
- `docs/stack/api-fastapi.md` or `docs/stack/api-hono.md` — admin + health HTTP layer
- `docs/stack/tracing-langfuse.md` — trace propagation from event payload through tool calls
- `docs/stack/secrets-management.md` — Resy / OpenTable / Toast credential handling, JWT signing key, DB URL

**Production concerns (load for Tier 3):**
- `docs/cross-cutting/logging-structured.md` · `docs/cross-cutting/observability.md` · `docs/cross-cutting/testing-strategy.md` · `docs/cross-cutting/auth-jwt.md` (admin endpoints)
- `docs/cross-cutting/idempotency.md` · `docs/cross-cutting/resilience.md` · `docs/cross-cutting/backpressure.md` · `docs/cross-cutting/dlq-operations.md` · `docs/cross-cutting/health-graceful-shutdown.md`
- `docs/cross-cutting/security-hardening.md` · `docs/cross-cutting/authorization-rbac.md` · `docs/cross-cutting/audit-logging.md` · `docs/cross-cutting/pii-gdpr.md` · `docs/cross-cutting/cost-tracking.md` · `docs/cross-cutting/model-routing.md`

**Scaffolding:** `docs/reference/docker-templates.md` · `docs/reference/docker-compose-template.md`

## What it does

A real-time rebooking agent for restaurant reservation platforms. When a reservation is cancelled, the agent:

1. Consumes the cancellation event from a Redis Stream (`reservations.cancelled`).
2. Enriches: fetches the current waitlist for that time slot, customer preferences for the original party, and availability across the restaurant.
3. Decides: chooses the best rebooking action — fill the slot from the waitlist, offer the original party an alternative time, notify the host, or do nothing if no good option exists.
4. Acts via tools: notifies the chosen customer (SMS/email), modifies the reservation, marks the slot as filled.
5. Emits a `reservations.rebooked` outcome event for downstream consumers (analytics, host UI updates).
6. Persists the decision + outcome to Postgres for audit.

SLO target: 60 seconds from cancellation event to first customer notification. Idempotent on `event_id` — duplicate cancellation events do not cause duplicate notifications.

This implements **event-driven multi-agent (flat)** — one orchestrator agent reasons about the rebooking, calling specialized tools for enrichment and action. The "specialists" are tools rather than separate agents; a future v2 may split them into peer agents (waitlist-matcher, host-notifier, alt-time-offerer) once the per-stage prompts grow large enough to justify the token cost.

## Architecture

```
   Reservation platform (Resy / OpenTable / Toast)
                       │
                       │  webhook / poll
                       v
              ┌──────────────────┐
              │ Producer service │  (out of scope — assumed to exist)
              └─────────┬────────┘
                        │  XADD
                        v
              ┌────────────────────────┐
              │ Redis Stream:          │
              │  reservations.cancelled│
              └─────────┬──────────────┘
                        │ XREADGROUP (consumer group: "rebooker")
                        v
            ┌─────────────────────────────┐
            │   Idempotency check (Redis) │
            └─────────┬───────────────────┘
                      │ (new event)
                      v
        ┌────────────────────────────────────┐
        │   LangGraph rebooking orchestrator │
        │                                    │
        │   Tools:                           │
        │   - get_waitlist                   │
        │   - get_customer_preferences       │
        │   - check_availability             │
        │   - notify_customer                │
        │   - modify_reservation             │
        │   - emit_outcome_event             │
        └────────────────┬───────────────────┘
                         │
            ┌────────────┼───────────┐
            v            v           v
       [Postgres]   [Reservation     [Redis Stream:
        outcomes]    platform via     reservations.rebooked]
                     ReservationAdapter
                     (Mock / Resy /
                     OpenTable / Toast)

   DLQ path: after 3 retries → XADD to reservations.cancelled.dlq
```

### Event flow

1. Producer service (out of scope) receives a webhook from the reservation platform and `XADD`s a normalized `CancellationEvent` onto `reservations.cancelled`.
2. The rebooker consumer group reads with `XREADGROUP`. Each worker takes a batch (10 events, 5s block).
3. For each event: `SET idemp:<event_id> 1 EX 86400 NX`. If the SET returns false, the event is a duplicate — `XACK` and continue.
4. The LangGraph orchestrator runs: enrich → decide → act → persist → emit.
5. On success: `XACK` the source event, `XADD` the outcome to `reservations.rebooked`, insert a row into `rebooking_outcomes`.
6. On retryable failure: do not `XACK`; the event becomes pending and `XCLAIM` picks it up after `idle-ms`. After `MAX_RETRIES` deliveries, the event is `XADD`ed to `reservations.cancelled.dlq` and `XACK`ed from the source.

## Data Models

### Python (Pydantic)

```python
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class CancellationReason(str, Enum):
    customer = "customer_cancelled"
    no_show = "no_show"
    restaurant = "restaurant_cancelled"
    weather = "weather"
    unknown = "unknown"


class CancellationEvent(BaseModel):
    event_id: str = Field(..., description="Producer-assigned UUID; partition key for idempotency")
    schema_version: int = Field(default=1)
    restaurant_id: str
    reservation_id: str
    party_size: int = Field(..., ge=1, le=50)
    reservation_time: datetime
    cancelled_at: datetime
    reason: CancellationReason
    customer_id: str | None = Field(default=None, description="Null for anonymous bookings")
    trace_id: str = Field(..., description="Propagate through all downstream tool calls")
    payload: dict = Field(default_factory=dict, description="Source-platform-specific fields")


class WaitlistEntry(BaseModel):
    customer_id: str
    party_size: int
    desired_time_window_start: datetime
    desired_time_window_end: datetime
    notify_channel: str = Field(..., description="sms | email")
    priority: int = Field(default=0)


class CustomerPreference(BaseModel):
    customer_id: str
    preferred_times: list[str] = Field(default_factory=list, description='e.g. ["19:00", "19:30"]')
    flexibility_minutes: int = Field(default=30, ge=0, le=240)
    notify_channel: str = Field(default="email")


class RebookingAction(str, Enum):
    fill_from_waitlist = "fill_from_waitlist"
    offer_alternative_time = "offer_alternative_time"
    notify_host_only = "notify_host_only"
    no_action = "no_action"


class RebookingDecision(BaseModel):
    action: RebookingAction
    target_customer_id: str | None = None
    new_reservation_time: datetime | None = None
    rationale: str = Field(..., description="LLM reasoning for the chosen action")


class RebookingOutcome(BaseModel):
    event_id: str = Field(..., description="Source cancellation event_id")
    restaurant_id: str
    reservation_id: str
    decision: RebookingDecision
    notified_customer_id: str | None
    notification_status: str = Field(..., description="sent | failed | skipped")
    new_reservation_id: str | None
    completed_at: datetime
    trace_id: str
```

### TypeScript (Zod)

```typescript
import { z } from "zod";

export const CancellationReason = z.enum([
  "customer_cancelled",
  "no_show",
  "restaurant_cancelled",
  "weather",
  "unknown",
]);

export const CancellationEvent = z.object({
  event_id: z.string(),
  schema_version: z.number().default(1),
  restaurant_id: z.string(),
  reservation_id: z.string(),
  party_size: z.number().int().min(1).max(50),
  reservation_time: z.string().datetime(),
  cancelled_at: z.string().datetime(),
  reason: CancellationReason,
  customer_id: z.string().nullable().default(null),
  trace_id: z.string(),
  payload: z.record(z.unknown()).default({}),
});

export const WaitlistEntry = z.object({
  customer_id: z.string(),
  party_size: z.number().int().min(1),
  desired_time_window_start: z.string().datetime(),
  desired_time_window_end: z.string().datetime(),
  notify_channel: z.enum(["sms", "email"]),
  priority: z.number().int().default(0),
});

export const CustomerPreference = z.object({
  customer_id: z.string(),
  preferred_times: z.array(z.string()).default([]),
  flexibility_minutes: z.number().int().min(0).max(240).default(30),
  notify_channel: z.enum(["sms", "email"]).default("email"),
});

export const RebookingAction = z.enum([
  "fill_from_waitlist",
  "offer_alternative_time",
  "notify_host_only",
  "no_action",
]);

export const RebookingDecision = z.object({
  action: RebookingAction,
  target_customer_id: z.string().nullable().default(null),
  new_reservation_time: z.string().datetime().nullable().default(null),
  rationale: z.string(),
});

export const RebookingOutcome = z.object({
  event_id: z.string(),
  restaurant_id: z.string(),
  reservation_id: z.string(),
  decision: RebookingDecision,
  notified_customer_id: z.string().nullable(),
  notification_status: z.enum(["sent", "failed", "skipped"]),
  new_reservation_id: z.string().nullable(),
  completed_at: z.string().datetime(),
  trace_id: z.string(),
});
```

## API Contract

The event-driven entry point has no HTTP API for the rebooking flow itself. The HTTP layer is for ops:

### `GET /health`

Liveness + readiness. Returns `200` only when Redis and Postgres are reachable AND the consumer is reading from the stream within the last 30 seconds. Otherwise `503`.

```json
{ "status": "ok", "last_event_seen_seconds_ago": 2 }
```

### `GET /metrics`

Prometheus-format metrics:

- `rebooker_events_processed_total{action="..."}`
- `rebooker_events_dlq_total{reason="..."}`
- `rebooker_e2e_latency_seconds_bucket{le="..."}`
- `rebooker_tool_calls_total{tool="..."}`

### `POST /admin/replay` (admin-authed)

Body: `{ "event_id": "evt-abc123" }`. Re-publishes a single event from the audit table back onto the input stream. For ops use after fixing a bug.

### `GET /admin/dlq?limit=N` (admin-authed)

Returns the N oldest entries in the DLQ stream with their failure metadata.

```json
{
  "entries": [
    {
      "msg_id": "1747...-0",
      "event_id": "evt-bad42",
      "first_seen_at": "2026-05-21T18:01:00Z",
      "attempts": 3,
      "last_error": "modify_reservation: 502 Bad Gateway"
    }
  ]
}
```

**Errors:**

| Status | Body | When |
|--------|------|------|
| 401 | `{"error": "unauthorized"}` | Admin endpoints without valid JWT |
| 404 | `{"error": "event_not_found"}` | `/admin/replay` with unknown `event_id` |
| 503 | `{"status": "degraded", ...}` | Health probe when Redis or Postgres is unreachable |

## Tool Specifications

### `get_waitlist`

| Field | Value |
|-------|-------|
| **Description** | Fetch the current waitlist entries for a restaurant overlapping a time window. Read-only; safe to call multiple times. |
| **Parameters** | `restaurant_id: str`, `time_window_start: datetime`, `time_window_end: datetime` |
| **Return type** | `list[WaitlistEntry]` — ordered by priority, then by `created_at`. |
| **Idempotency** | Pure read. |

### `get_customer_preferences`

| Field | Value |
|-------|-------|
| **Description** | Look up a customer's stored time preferences and flexibility. Read-only. |
| **Parameters** | `customer_id: str` |
| **Return type** | `CustomerPreference \| None` (None if no record). |
| **Idempotency** | Pure read. |

### `check_availability`

| Field | Value |
|-------|-------|
| **Description** | Ask the reservation platform whether a party size can be seated at a given time. Read-only against the platform. |
| **Parameters** | `restaurant_id: str`, `party_size: int`, `time: datetime` |
| **Return type** | `bool` |
| **Idempotency** | Pure read. |

### `notify_customer`

| Field | Value |
|-------|-------|
| **Description** | Send an SMS or email to a customer. **Idempotent on `idempotency_key`** — the adapter dedupes within a 24h window. |
| **Parameters** | `customer_id: str`, `channel: "sms" \| "email"`, `message: str`, `idempotency_key: str` (set to the cancellation `event_id`) |
| **Return type** | `NotificationResult` with `status: "sent" \| "failed" \| "skipped"`. |
| **Idempotency** | The `NotificationChannel` adapter MUST persist `(idempotency_key, channel)` and short-circuit duplicates. |

### `modify_reservation`

| Field | Value |
|-------|-------|
| **Description** | Mutate a reservation: release, fill from waitlist, or move. **Idempotent on `idempotency_key`**. |
| **Parameters** | `reservation_id: str`, `action: "release" \| "fill" \| "move"`, `payload: dict`, `idempotency_key: str` |
| **Return type** | `ReservationModificationResult` with `new_reservation_id: str \| None`. |
| **Idempotency** | The `ReservationPlatform` adapter MUST dedupe — real platforms generally support an idempotency header (Stripe-style). |

### `emit_outcome_event`

| Field | Value |
|-------|-------|
| **Description** | `XADD` a `RebookingOutcome` to the outcome stream for downstream consumers. |
| **Parameters** | `outcome: RebookingOutcome` |
| **Return type** | `None` |
| **Idempotency** | Stream is append-only; `event_id` field on the payload makes downstream dedup possible. |

Note that action tools take an `idempotency_key` — the adapter implementation must dedupe. Without this, redelivery from Redis (after a crash between the tool call and the `XACK`) would cause duplicate notifications.

## Prompt Specifications

### Orchestrator system prompt

```
You are a real-time rebooking coordinator for a restaurant. A reservation has just been cancelled. Your job is to decide what to do about the now-empty time slot AND the original party (if they cancelled — they may want a different time).

You will be given:
- The cancellation event details
- The current waitlist for the relevant time window (if any)
- The original customer's stored preferences (if known)
- The restaurant's availability around the cancelled time

Choose ONE action from the following:

1. **fill_from_waitlist** — A waitlist customer matches party size and time window. Notify them; modify the reservation; emit outcome.
2. **offer_alternative_time** — No waitlist match, but the original customer (if it was customer-cancelled they likely don't want this; if no-show or restaurant-cancelled, they might) has stored preferences indicating flexibility. Offer them a different time.
3. **notify_host_only** — No good rebooking option. Just notify the restaurant host that the slot opened up.
4. **no_action** — The cancellation was inside the no-action window (e.g., <15 minutes before the time, slot can't realistically be filled). Log and exit.

Rules:
- Be conservative. If two options both seem viable, prefer the one that disturbs fewer customers.
- Never contact the original customer if reason is "customer_cancelled" — they just chose to leave.
- Always include your reasoning in the `rationale` field.

Return a `RebookingDecision` object.
```

**Design rationale:** The prompt is load-bearing — preserve it verbatim. It encodes the action enum, the precedence between actions, and a small set of policy rules (no-action window, don't re-contact a customer who cancelled). The LLM's freedom is bounded to selecting one of four enum values plus a target customer; everything else is structured output. The `rationale` field is required so audit logs and the eval suite can inspect reasoning.

## Key files

> Follows the canonical [project layout](../cross-cutting/project-layout.md) — `app/` package for Python, `src/` for TypeScript, `tests/{unit,integration,eval}/` for both.

### Python track

| File | Role |
|------|------|
| `src/{project_name}/main.py` | Entrypoint: configure logging, build adapters, start consumer loop. Exports `agent` for smoke-check import. |
| `src/{project_name}/settings.py` | pydantic-settings: env-var-backed config (Redis URL, Postgres URL, stream + group names, retry knobs). |
| `src/{project_name}/consumer/redis_streams.py` | Consumer loop: `XREADGROUP`, idempotency check, dispatch to orchestrator, ACK/DLQ. |
| `src/{project_name}/orchestrator/graph.py` | LangGraph state machine: enrich → decide → act → persist → emit. |
| `src/{project_name}/orchestrator/prompts.py` | System prompt (see Prompt Specifications). |
| `src/{project_name}/tools/enrichment.py` | `get_waitlist`, `get_customer_preferences`, `check_availability`. |
| `src/{project_name}/tools/actions.py` | `notify_customer`, `modify_reservation`, `emit_outcome_event`. |
| `src/{project_name}/adapters/reservation_platform.py` | `ReservationPlatform` ABC + `MockReservationPlatform` (v1). Resy/OpenTable/Toast subclasses are stubs for v2. |
| `src/{project_name}/adapters/notification.py` | `NotificationChannel` ABC + Mock implementation (SMS/email stubs that log only). |
| `src/{project_name}/models/events.py` | Pydantic models (see Data Models). |
| `src/{project_name}/db/models.py` | SQLAlchemy: `RebookingOutcome` table. |
| `src/{project_name}/db/migrations/` | Alembic migrations. |
| `src/{project_name}/api/admin.py` | FastAPI router: `/health`, `/metrics`, `/admin/replay`, `/admin/dlq`. |
| `src/{project_name}/observability/tracing.py` | Langfuse integration; `trace_id` propagation from event payload through tool calls. |
| `tests/unit/test_orchestrator.py` | Mock the LLM; assert state-machine transitions for each action. |
| `tests/integration/test_event_loop.py` | Spin up real Redis (via testcontainers or docker-compose); publish events; assert outcomes. |
| `tests/eval/test_rebooking_decisions.py` | Golden dataset: 20+ cancellation scenarios with expected decisions; eval via DeepEval or Promptfoo. |
| `tests/fixtures/cancellation_events.json` | Sample events for tests. |
| `Dockerfile` | Multi-stage; final image <200MB. |
| `docker-compose.yml` | Redis 7, Postgres 16, Langfuse, the app. |
| `.github/workflows/ci.yml` | Lint (ruff), type-check (mypy), tests (pytest). |
| `.env.example` | All env vars with comments. |
| `README.md` | Prereqs, install, env setup, run, test, architecture overview. |
| `pyproject.toml` | Manifest. |

### TypeScript track

| File | Role |
|------|------|
| `src/index.ts` | Entrypoint: configure logging, build adapters, start consumer loop. |
| `src/config.ts` | Zod-validated config from env. |
| `src/consumer/redisStreams.ts` | `xreadgroup` loop, idempotency, dispatch, ACK/DLQ. |
| `src/orchestrator/workflow.ts` | Mastra workflow with enrich/decide/act/persist/emit steps. |
| `src/orchestrator/prompts.ts` | System prompt. |
| `src/tools/enrichment.ts` | `getWaitlist`, `getCustomerPreferences`, `checkAvailability`. |
| `src/tools/actions.ts` | `notifyCustomer`, `modifyReservation`, `emitOutcomeEvent`. |
| `src/adapters/reservationPlatform.ts` | `ReservationPlatform` interface + `MockReservationPlatform`. |
| `src/adapters/notification.ts` | `NotificationChannel` interface + Mock implementation. |
| `src/schemas/events.ts` | Zod schemas. |
| `src/db/schema.ts` | Drizzle schema: `rebooking_outcomes`. |
| `src/api/admin.ts` | Hono router with `/health`, `/metrics`, `/admin/replay`, `/admin/dlq`. |
| `tests/unit/orchestrator.test.ts` · `tests/integration/eventLoop.test.ts` · `tests/eval/rebookingDecisions.test.ts` | Three-tier test suite (vitest). |

## Implementation Roadmap

| Step | Task | Key deliverables |
|------|------|-----------------|
| 1 | **Project scaffolding** | Settings (pydantic-settings / zod), structured logging, `.env.example`. |
| 2 | **Data models + DB schema** | Pydantic + Zod models; SQLAlchemy/Drizzle table for `rebooking_outcomes`; Alembic migration. |
| 3 | **Mock adapters** | `MockReservationPlatform`, `MockNotificationChannel` — so end-to-end works without external APIs. |
| 4 | **Tools** | Enrichment + action tools, wired to the mock adapters; idempotency key plumbed through. |
| 5 | **Orchestrator** | LangGraph (or Mastra) state machine + system prompt; returns `RebookingDecision`. |
| 6 | **Consumer loop** | Redis Streams: `XREADGROUP`, idempotency `SET NX`, dispatch, ACK; pending-message reaper via `XCLAIM`; DLQ on retry exhaustion. |
| 7 | **Admin HTTP layer** | FastAPI / Hono router for `/health`, `/metrics`, `/admin/replay`, `/admin/dlq`. |
| 8 | **Observability** | Langfuse integration; structlog (Py) / pino (TS); trace_id propagation from event payload. |
| 9 | **Tests** | Unit (mocked LLM) → integration (real Redis + Postgres) → eval (real LLM, golden dataset). |
| 10 | **Dockerfile + docker-compose** | Multi-stage image; Redis 7, Postgres 16, Langfuse, the app. |
| 11 | **CI workflow** | Lint, type-check, three-tier tests. |

## Environment & Deployment

### Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | LLM credential |
| `MODEL` | No | `claude-sonnet-4-6` | LLM model |
| `REDIS_URL` | No | `redis://localhost:6379` | Event stream + idempotency |
| `EVENT_STREAM` | No | `reservations.cancelled` | Input stream name |
| `OUTCOME_STREAM` | No | `reservations.rebooked` | Output stream name |
| `DLQ_STREAM` | No | `reservations.cancelled.dlq` | Dead-letter stream |
| `CONSUMER_GROUP` | No | `rebooker` | Redis consumer group |
| `CONSUMER_NAME` | No | (auto, e.g. hostname) | Consumer ID within the group |
| `IDEMPOTENCY_TTL_SECONDS` | No | `86400` | Full dedup window after successful completion; must exceed event-source retention |
| `IDEMPOTENCY_CLAIM_TTL_SECONDS` | No | `300` | Short TTL while a worker is processing; expires if the worker crashes |
| `MAX_RETRIES` | No | `3` | Retries before DLQ |
| `CLAIM_MIN_IDLE_MS` | No | `60000` | `XCLAIM` minimum idle time before reclaiming a pending event |
| `POSTGRES_URL` | No | `postgresql+asyncpg://agent:agent@localhost:5432/agent_db` | Outcomes + audit |
| `LANGFUSE_PUBLIC_KEY` | No | `pk-lf-local` | Tracing |
| `LANGFUSE_SECRET_KEY` | No | `sk-lf-local` | Tracing |
| `LANGFUSE_HOST` | No | `http://localhost:3000` | Langfuse server URL |
| `ADMIN_JWT_SECRET` | Yes (prod) | `change-me-in-production` | Admin HTTP auth |
| `SLO_NOTIFICATION_SECONDS` | No | `60` | SLO target for first notification |
| `APP_ENV` | No | `development` | Environment name |
| `LOG_LEVEL` | No | `INFO` | Log level |

### Docker Compose

See [Docker Compose template](../reference/docker-compose-template.md) for base infrastructure. This agent needs: Redis 7-alpine, Postgres 16, Langfuse, the app. Each service has a healthcheck; the app depends on Redis + Postgres healthy.

### Infrastructure dependencies

| Component | Required? | Why |
|-----------|-----------|-----|
| Redis | Yes | Event source (Streams) + idempotency store |
| Postgres | Yes | Outcomes + audit log; needed by `/admin/replay` |
| Langfuse | Recommended | LLM + tool call tracing (skip for local dev) |
| Real reservation platform | No (v1) | Mock adapter ships with the recipe; Resy/OpenTable/Toast are stubs |

## Seed data

The LLM should emit `scripts/seed.py` so that a freshly-generated project boots into a working demo state on the first `agent-scaffold up`. The script populates each declared capability's local store:

- **Postgres (`relational.postgres`)** — insert ~50 sample restaurants (`id`, `name`, `city`, `cuisine`, `party_capacity`) and ~80 reservations spread across them (most `active`, ~20% `cancelled`). Use `INSERT ... ON CONFLICT (id) DO NOTHING` so re-runs are safe.
- **Qdrant (`vector_db.qdrant`)** — create a `docs` collection (1536 dims, cosine distance) and upsert one point per restaurant whose payload is the description and whose vector is the embedded description. Skip recreation if the collection already exists; upserts are idempotent on point `id`.
- **Redis Streams (`queue.redis-streams`)** — publish 3 sample `reservation.cancelled` events onto the `reservations.cancelled` stream using `XADD ... MAXLEN ~ 100 *` so the agent has something to react to immediately and the stream stays bounded on repeated seeds.

Each block should log "skipped (already seeded)" vs. "seeded N rows / points / events" so a re-run is visibly idempotent. The script is invoked as the last step of `agent-scaffold up` (after `bootstrap_*` steps complete) and is safe to run by hand at any point.

## Lifecycle

After generation, four `agent-scaffold` commands cover the full local-demo lifecycle. Surface these verbatim in the generated project's `README.md`:

1. `agent-scaffold up` — start the compose stack, run all `bootstrap_*` steps (datasources, dashboards, collections, consumer groups), then run `scripts/seed.py`.
2. `agent-scaffold status` — show the health of every capability service (Redis, Postgres, Qdrant, Langfuse, Grafana) and the last consumer offset.
3. `agent-scaffold deploy --target vercel --dry-run` — render the `host.vercel` deploy plan (env-var diff, build command, project link) without pushing.
4. `agent-scaffold down` — stop the compose stack and (optionally) prune volumes.

The new generation system prompt requires this list to appear in the recipe; the scaffolded README inherits it so users have a single canonical sequence.

## Test Strategy

### Tier 1 — unit (no I/O, mocked LLM)

```python
def test_orchestrator_picks_fill_from_waitlist(mock_llm):
    """Given a matching waitlist entry, the graph chooses fill_from_waitlist."""
    state = build_state(
        event=cancellation_event(party_size=4),
        waitlist=[waitlist_entry(party_size=4)],
    )
    mock_llm.set_decision(action=RebookingAction.fill_from_waitlist, target_customer_id="c1")
    decision = run_orchestrator(state)
    assert decision.action == RebookingAction.fill_from_waitlist
    assert decision.target_customer_id == "c1"


def test_duplicate_event_short_circuits(mock_redis):
    """Second delivery of the same event_id returns without invoking the orchestrator."""
    await mock_redis.set("idemp:evt-1", "1", ex=86400, nx=True)
    invocations = await handle_event(cancellation_event(event_id="evt-1"))
    assert invocations.orchestrator_called is False
```

- `tests/unit/test_orchestrator.py` — assert the state graph chooses each `RebookingAction` correctly given mocked enrichment-tool outputs.
- `tests/unit/test_idempotency.py` — duplicate `event_id` returns immediately without invoking the orchestrator.
- `tests/unit/test_models.py` — Pydantic validation: rejects out-of-range `party_size`, missing `trace_id`, bad enums.

### Tier 2 — integration (real Redis + Postgres, mocked LLM + mocked platform)

- `tests/integration/test_event_loop.py` — publish a cancellation event; assert (a) outcome event is emitted on the outcome stream, (b) Postgres row written, (c) notification tool called exactly once.
- `tests/integration/test_retry_dlq.py` — make `modify_reservation` raise transient errors; assert `MAX_RETRIES` retries; force permanent failure; assert event ends up on DLQ.
- `tests/integration/test_xclaim_reaper.py` — kill a worker mid-flight; assert another worker reclaims the pending event after `CLAIM_MIN_IDLE_MS`.

### Tier 3 — eval (real LLM, golden dataset)

- `tests/eval/test_rebooking_decisions.py` — golden dataset of 20+ scenarios. For each: cancellation event + world state → expected `RebookingAction` (and optionally `target_customer_id`). Pass threshold: **90%+ exact-match on action; 80%+ on (action + target_customer_id)**. Failures below threshold fail CI.

## Eval Dataset

Five seed examples are inline below. The scaffold step should generate ~15 more to reach the 20-example minimum.

```json
[
  {
    "name": "waitlist-match-exact",
    "event": {
      "event_id": "evt-eval-1",
      "restaurant_id": "rest-99",
      "reservation_id": "res-1",
      "party_size": 4,
      "reservation_time": "2026-05-21T19:30:00Z",
      "cancelled_at": "2026-05-21T18:00:00Z",
      "reason": "customer_cancelled",
      "trace_id": "trace-1"
    },
    "world": {
      "waitlist": [
        {
          "customer_id": "c1",
          "party_size": 4,
          "desired_time_window_start": "2026-05-21T19:00:00Z",
          "desired_time_window_end": "2026-05-21T20:00:00Z",
          "notify_channel": "sms",
          "priority": 10
        }
      ]
    },
    "expected": { "action": "fill_from_waitlist", "target_customer_id": "c1" }
  },
  {
    "name": "no-waitlist-no-preferences",
    "event": {
      "event_id": "evt-eval-2",
      "restaurant_id": "rest-99",
      "reservation_id": "res-2",
      "party_size": 2,
      "reservation_time": "2026-05-21T20:00:00Z",
      "cancelled_at": "2026-05-21T18:30:00Z",
      "reason": "no_show",
      "trace_id": "trace-2"
    },
    "world": { "waitlist": [], "customer_preferences": null },
    "expected": { "action": "notify_host_only" }
  },
  {
    "name": "cancellation-inside-no-action-window",
    "event": {
      "event_id": "evt-eval-3",
      "restaurant_id": "rest-99",
      "reservation_id": "res-3",
      "party_size": 2,
      "reservation_time": "2026-05-21T19:00:00Z",
      "cancelled_at": "2026-05-21T18:50:00Z",
      "reason": "customer_cancelled",
      "trace_id": "trace-3"
    },
    "world": {},
    "expected": { "action": "no_action" }
  },
  {
    "name": "restaurant-cancelled-offer-alternative",
    "event": {
      "event_id": "evt-eval-4",
      "restaurant_id": "rest-99",
      "reservation_id": "res-4",
      "party_size": 2,
      "customer_id": "c-orig",
      "reservation_time": "2026-05-21T19:30:00Z",
      "cancelled_at": "2026-05-21T16:00:00Z",
      "reason": "restaurant_cancelled",
      "trace_id": "trace-4"
    },
    "world": {
      "waitlist": [],
      "customer_preferences": {
        "customer_id": "c-orig",
        "preferred_times": ["19:00", "20:00"],
        "flexibility_minutes": 60,
        "notify_channel": "email"
      },
      "alternative_slots": ["2026-05-21T20:00:00Z"]
    },
    "expected": { "action": "offer_alternative_time", "target_customer_id": "c-orig" }
  },
  {
    "name": "waitlist-party-size-mismatch",
    "event": {
      "event_id": "evt-eval-5",
      "restaurant_id": "rest-99",
      "reservation_id": "res-5",
      "party_size": 2,
      "reservation_time": "2026-05-21T19:30:00Z",
      "cancelled_at": "2026-05-21T18:00:00Z",
      "reason": "customer_cancelled",
      "trace_id": "trace-5"
    },
    "world": {
      "waitlist": [
        {
          "customer_id": "c2",
          "party_size": 6,
          "desired_time_window_start": "2026-05-21T19:00:00Z",
          "desired_time_window_end": "2026-05-21T20:00:00Z",
          "notify_channel": "email",
          "priority": 5
        }
      ]
    },
    "expected": { "action": "notify_host_only" }
  }
]
```

Generate the remaining ~15 examples at scaffold time covering: customer-cancelled with both waitlist and preferences (waitlist wins), weather cancellations with multiple waitlist priorities, party-size partial overlap (4 → 3 acceptable?), time-window edge cases, multiple-language notification channels, anonymous booking (no `customer_id`), bookings outside operating hours.

See [eval-data guide](../cross-cutting/eval-data.md) for generation + curation patterns.

## Design Decisions

- **Event-driven over polling:** Cancellations happen at a few-per-minute rate per restaurant; the SLO is 60 seconds. A polling cron at <60s intervals would either waste calls or miss the SLO. Streams give push-shaped delivery with durable replay.
- **LangGraph over CrewAI:** Each rebooking is a deterministic state machine (enrich → decide → act → persist → emit) with explicit retry boundaries between steps. LangGraph models this directly; CrewAI's collaborative-agents abstraction adds inter-agent chatter that this single-decision flow doesn't need.
- **Mock-first adapters:** Real reservation platforms have rate limits, OAuth flows, and sandbox/prod splits. Mocks let CI run end-to-end and let v1 demo the full flow without contracts in place.
- **Redis Streams over Kafka (today):** Throughput is well under 10k events/sec per restaurant chain; we're already running Redis for idempotency; one fewer service to operate. **Migration path:** when sustained throughput on any single stream pushes past ~5k events/sec — or when a second team needs the same stream — swap to Kafka (see [stack/kafka.md](../stack/kafka.md)) and adopt the [schema-evolution](../cross-cutting/schema-evolution.md) discipline at registry scale. The consumer-loop abstraction in `consumer/redis_streams.py` is small enough that a parallel `consumer/kafka.py` is the right migration shape.
- **No separate sub-agents for v1:** The orchestrator has six tools but one decision. Splitting it into waitlist-matcher / host-notifier / alt-time-offerer agents would add agent-to-agent token cost without quality gain at this scale. Promote to peer agents only if a stage's prompt grows past ~500 tokens of guidance.
- **Idempotency on `event_id` end-to-end:** The same key is used by the consumer-side Redis SET, the notification adapter, and the reservation adapter. One key, three checkpoints; redelivery is safe at any point in the flow.
- **Two-phase idempotency:** A short-TTL "claimed" marker is set before the orchestrator runs; the marker is upgraded to "completed" (long TTL) on success or deleted on failure. This prevents the bug where a crashed worker between SETNX and XACK silently dedupes the event on the next delivery.
- **`trace_id` in event payload:** Producer assigns it. The consumer reads it into the Langfuse trace context so every tool call in this rebooking is linked to the originating cancellation across services.
- **Multi-tenancy via `restaurant_id`:** Every record (outcomes, audit rows, idempotency keys) is keyed by `restaurant_id`. Shared schema with planned Postgres RLS adoption — see [multi-tenancy.md](../cross-cutting/multi-tenancy.md). Per-restaurant rate limits prevent one noisy chain from DoSing the rest; per-tenant log / trace fields keep incident investigation tractable.

## Generation instructions

These instructions apply to the LLM emitting the project, **not** to the runtime behavior of the generated agent.

### Smoke check override (required)

The default Python language-hint smoke check is `uv run python -c 'from {project_name}.main import agent; print("ok")'`. That shape assumes a request/response agent — wrong for an event-driven consumer. **Override `smoke_check` in your generation output to:**

```
uv run python -c 'from {project_name}.orchestrator.graph import build_graph; build_graph(); print("ok")'
```

For TypeScript, override to:

```
pnpm exec tsx -e "import { buildGraph } from './src/orchestrator/workflow'; buildGraph(); console.log('ok')"
```

These verify the orchestrator wires up without requiring Redis, Postgres, or any external service to be running.

### Entry-point shape

`main.py` (Python) and `src/index.ts` (TypeScript) should:

- **Not** export an importable `agent` symbol.
- Run the consumer loop under `if __name__ == "__main__":` (Python) or `import.meta.url === ...` (TS):

```python
# src/{project_name}/main.py
import asyncio
import structlog
from {project_name}.consumer.redis_streams import run_consumer
from {project_name}.settings import settings

logger = structlog.get_logger()

async def main() -> None:
    logger.info("rebooker_starting", env=settings.app_env)
    await run_consumer()

if __name__ == "__main__":
    asyncio.run(main())
```

### Dependency hygiene

Every dependency in the project's manifest (`pyproject.toml` / `package.json`) must be present in either the language hints' `pinned_dependencies` or the recipe's `recipe_dependencies`. Do not invent additional packages.

If you genuinely need a package that isn't listed, **stop and emit a `known_limitations` entry** rather than silently adding it — the maintainer will then add it to the recipe and re-scaffold.

### Tests must be runnable without external services

- `tests/unit/*` — use `monkeypatch` / `pytest-mock` to stub the LLM and Redis. No network, no Docker.
- `tests/integration/*` — use `pytest` markers (e.g. `@pytest.mark.integration`) so they're opt-in. They may use `testcontainers` if listed in `recipe_dependencies`; otherwise document that they require `docker compose up` first.
- `tests/eval/*` — use a `pytest.skip("set ANTHROPIC_API_KEY")` fixture-level guard so they don't fail in CI without a key. The golden dataset itself (`tests/fixtures/eval_dataset.json`) should be checked in.

## Reference Implementation (pseudocode)

Since this is a fresh "design spec" recipe (not "validated"), the snippets below are pseudocode for the load-bearing pieces — the consumer loop and the orchestrator state graph. Generate the rest of the project from the file-by-file table.

<details>
<summary><code>src/{project_name}/consumer/redis_streams.py</code> (pseudocode)</summary>

```python
"""Redis Streams consumer loop with idempotency, retries, and DLQ."""

import asyncio

import redis.asyncio as redis
import structlog

from {project_name}.orchestrator.graph import run_orchestrator
from {project_name}.settings import settings

logger = structlog.get_logger()


async def run_consumer() -> None:
    client = redis.from_url(settings.redis_url)
    stream = settings.event_stream
    group = settings.consumer_group
    consumer = settings.consumer_name

    try:
        await client.xgroup_create(stream, group, id="$", mkstream=True)
    except redis.ResponseError:
        pass  # group exists

    while True:
        msgs = await client.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: ">"},
            count=10,
            block=5000,
        )
        for _stream, entries in msgs or []:
            for msg_id, fields in entries:
                await _handle_one(client, msg_id, fields)


async def _handle_one(client, msg_id, fields) -> None:
    event_id = fields[b"event_id"].decode()
    log = logger.bind(event_id=event_id, msg_id=msg_id)
    idem_key = f"idemp:{event_id}"

    # Two-phase idempotency: claim with a short TTL; mark "completed" on success.
    # A crashed worker's "claimed" key expires, allowing redelivery to retry.
    claim_ttl_seconds = settings.idempotency_claim_ttl_seconds
    final_ttl_seconds = settings.idempotency_ttl_seconds

    claimed = await client.set(idem_key, "claimed", ex=claim_ttl_seconds, nx=True)
    if not claimed:
        status = await client.get(idem_key)
        if status == b"completed":
            log.info("duplicate_skipped")
            await client.xack(settings.event_stream, settings.consumer_group, msg_id)
            return
        # Another worker holds the claim; let it finish. XCLAIM reaper will
        # re-deliver to us if that worker dies before the claim expires.
        log.info("claim_held_by_other_worker")
        return

    # Retry budget for this worker's delivery
    pending = await client.xpending_range(
        settings.event_stream, settings.consumer_group,
        min=msg_id, max=msg_id, count=1,
    )
    attempts = pending[0]["times_delivered"] if pending else 1

    try:
        await run_orchestrator(fields)
        # Mark completed and extend TTL to the full dedup window
        await client.set(idem_key, "completed", ex=final_ttl_seconds)
        await client.xack(settings.event_stream, settings.consumer_group, msg_id)
    except Exception as exc:
        log.warning("handler_failed", attempts=attempts, error=str(exc))
        # Release the claim so retry (this worker or XCLAIM'd) can re-enter
        await client.delete(idem_key)
        if attempts >= settings.max_retries:
            await client.xadd(
                settings.dlq_stream,
                {**fields, b"last_error": str(exc).encode()},
            )
            await client.xack(settings.event_stream, settings.consumer_group, msg_id)
            log.error("event_dlqd")
        # else: leave un-ACKed; XCLAIM reaper will redeliver after CLAIM_MIN_IDLE_MS
```

</details>

<details>
<summary><code>src/{project_name}/orchestrator/graph.py</code> (pseudocode)</summary>

```python
"""LangGraph rebooking orchestrator: enrich -> decide -> act -> persist -> emit."""

from langgraph.graph import END, StateGraph

from {project_name}.models.events import CancellationEvent, RebookingAction, RebookingDecision
from {project_name}.orchestrator.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from {project_name}.tools.actions import emit_outcome_event, modify_reservation, notify_customer
from {project_name}.tools.enrichment import (
    check_availability,
    get_customer_preferences,
    get_waitlist,
)


async def enrich(state: dict) -> dict:
    event: CancellationEvent = state["event"]
    state["waitlist"] = await get_waitlist(
        event.restaurant_id,
        event.reservation_time,
        event.reservation_time,
    )
    state["preferences"] = (
        await get_customer_preferences(event.customer_id) if event.customer_id else None
    )
    state["availability"] = await check_availability(
        event.restaurant_id, event.party_size, event.reservation_time
    )
    return state


async def decide(state: dict) -> dict:
    # Call the LLM with ORCHESTRATOR_SYSTEM_PROMPT and the enriched state.
    # Use structured output bound to RebookingDecision.
    decision: RebookingDecision = await llm_decide(state, ORCHESTRATOR_SYSTEM_PROMPT)
    state["decision"] = decision
    return state


async def act(state: dict) -> dict:
    event: CancellationEvent = state["event"]
    decision: RebookingDecision = state["decision"]
    idem = event.event_id

    if decision.action == RebookingAction.fill_from_waitlist:
        await notify_customer(decision.target_customer_id, "sms", "...", idempotency_key=idem)
        result = await modify_reservation(event.reservation_id, "fill", {...}, idempotency_key=idem)
        state["new_reservation_id"] = result.new_reservation_id
    elif decision.action == RebookingAction.offer_alternative_time:
        await notify_customer(decision.target_customer_id, "email", "...", idempotency_key=idem)
    elif decision.action == RebookingAction.notify_host_only:
        await notify_customer("host", "email", "...", idempotency_key=idem)
    # no_action: pass
    return state


async def persist_and_emit(state: dict) -> dict:
    outcome = build_outcome(state)
    await write_outcome_row(outcome)
    await emit_outcome_event(outcome)
    return state


def build_graph() -> StateGraph:
    g = StateGraph(dict)
    g.add_node("enrich", enrich)
    g.add_node("decide", decide)
    g.add_node("act", act)
    g.add_node("persist", persist_and_emit)
    g.set_entry_point("enrich")
    g.add_edge("enrich", "decide")
    g.add_edge("decide", "act")
    g.add_edge("act", "persist")
    g.add_edge("persist", END)
    return g.compile()


_compiled = build_graph()


async def run_orchestrator(event_fields: dict) -> None:
    event = CancellationEvent.model_validate({k.decode(): v.decode() for k, v in event_fields.items()})
    await _compiled.ainvoke({"event": event})
```

</details>

<details>
<summary><code>src/{project_name}/adapters/reservation_platform.py</code> (interface only)</summary>

```python
"""ReservationPlatform ABC + MockReservationPlatform (v1).

Resy, OpenTable, and Toast subclasses are stubs in v1 — fill them in when contracts land.
"""

from abc import ABC, abstractmethod
from datetime import datetime


class ReservationModificationResult:
    def __init__(self, new_reservation_id: str | None, status: str) -> None:
        self.new_reservation_id = new_reservation_id
        self.status = status


class ReservationPlatform(ABC):
    @abstractmethod
    async def check_availability(self, restaurant_id: str, party_size: int, time: datetime) -> bool: ...

    @abstractmethod
    async def modify_reservation(
        self,
        reservation_id: str,
        action: str,
        payload: dict,
        idempotency_key: str,
    ) -> ReservationModificationResult: ...


class MockReservationPlatform(ReservationPlatform):
    """In-memory mock. Persists processed idempotency_keys to dedupe across redelivery."""

    def __init__(self) -> None:
        self._processed: dict[str, ReservationModificationResult] = {}

    async def check_availability(self, restaurant_id, party_size, time) -> bool:
        return True

    async def modify_reservation(self, reservation_id, action, payload, idempotency_key):
        if idempotency_key in self._processed:
            return self._processed[idempotency_key]
        result = ReservationModificationResult(new_reservation_id=f"new-{reservation_id}", status="ok")
        self._processed[idempotency_key] = result
        return result


# Stubs for v2 — populate when platform contracts land:
class ResyReservationPlatform(ReservationPlatform):
    async def check_availability(self, restaurant_id, party_size, time): raise NotImplementedError
    async def modify_reservation(self, reservation_id, action, payload, idempotency_key): raise NotImplementedError


class OpenTableReservationPlatform(ReservationPlatform):
    async def check_availability(self, restaurant_id, party_size, time): raise NotImplementedError
    async def modify_reservation(self, reservation_id, action, payload, idempotency_key): raise NotImplementedError


class ToastReservationPlatform(ReservationPlatform):
    async def check_availability(self, restaurant_id, party_size, time): raise NotImplementedError
    async def modify_reservation(self, reservation_id, action, payload, idempotency_key): raise NotImplementedError
```

</details>


## Example interaction

Publish a cancellation event:

```bash
redis-cli XADD reservations.cancelled '*' \
  event_id evt-abc123 \
  schema_version 1 \
  restaurant_id rest-99 \
  reservation_id res-42 \
  party_size 4 \
  reservation_time 2026-05-21T19:30:00Z \
  cancelled_at 2026-05-21T18:00:00Z \
  reason customer_cancelled \
  trace_id trace-xyz \
  payload '{}'
```

Within ~60 seconds, observe:

```bash
redis-cli XRANGE reservations.rebooked - +
# 1747850412-0  event_id evt-abc123  action fill_from_waitlist  notified_customer_id c1 ...

psql -c "SELECT event_id, action, notification_status FROM rebooking_outcomes WHERE event_id = 'evt-abc123';"
# evt-abc123 | fill_from_waitlist | sent
```
