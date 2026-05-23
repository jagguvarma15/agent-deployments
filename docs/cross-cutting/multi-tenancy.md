# Cross-cutting: Multi-tenancy

**Concern:** Per-tenant data isolation is load-bearing. Pick the model deliberately; cross-tenant leaks are catastrophic and silent — no exception, no alert, just the wrong customer's data returned.
**Library:** Postgres Row-Level Security (`pg_rls`); `structlog` contextvars; `slowapi` per-tenant key functions.
**Lives in:** Inline below — every recipe that serves more than one customer organisation adopts this.

## What it provides

- The three classic isolation models — separate DB / separate schema / shared schema — with one-line tradeoffs.
- A working Postgres RLS pattern that takes app-layer mistakes off the table.
- Tenant context propagation across HTTP, events, async tasks, logs, and traces.
- Per-tenant rate limits, quotas, and resource isolation beyond the data layer.
- An onboarding / suspension / offboarding playbook.
- Cross-tenant access tests — the single test class every multi-tenant service should have.

## Why this matters

A multi-tenant system serves many customers (tenants) from shared infrastructure. For mise: each restaurant chain is a tenant. Cross-tenant leaks are:

- **A regulatory issue** — GDPR Article 32 (security of processing), SOC 2 CC6 series.
- **A trust-destroying incident** — one chain sees another's reservations; recovery is contractual at best.
- **Often silent** — no exception, no error, just the wrong data returned. The leak is detected by the customer, not the system.

Designing for tenant isolation up front costs a little. Retrofitting it after a leak costs a lot.

## Three isolation models

| Model | Isolation | Cost | When to use |
|-------|-----------|------|-------------|
| **Separate database per tenant** | Strongest | High (per-tenant ops, backups, upgrades) | Few large tenants; compliance requires physical isolation |
| **Separate schema per tenant** | Strong | Medium (one DB, many schemas; migration fan-out) | Tens to low-hundreds of tenants |
| **Shared schema + `tenant_id` column** | Weakest (relies on discipline + RLS) | Lowest | Thousands+ of tenants; standard SaaS shape |

For mise: **shared schema with `restaurant_id`** on every tenant-owned table. Cheapest to operate; isolation enforced via application discipline + Postgres Row-Level Security so the DB itself rejects cross-tenant reads.

## Shared schema with Postgres RLS

Row-Level Security makes the DB enforce tenant isolation — application-layer bugs that forget the `WHERE tenant_id = ?` clause stop being leaks because the DB filters automatically.

```sql
ALTER TABLE rebooking_outcomes ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON rebooking_outcomes
    USING       (restaurant_id = current_setting('app.current_tenant_id')::uuid)
    WITH CHECK  (restaurant_id = current_setting('app.current_tenant_id')::uuid);
```

`USING` filters reads; `WITH CHECK` rejects writes that try to insert / update rows for a different tenant.

Application sets the tenant per request:

```python
async with get_db() as session:
    await session.execute(
        text("SET LOCAL app.current_tenant_id = :tid"),
        {"tid": str(tenant_id)},
    )
    # Every query on this session is now auto-filtered
    rows = await session.execute(select(RebookingOutcome))
```

**Critical:** use `SET LOCAL` (transaction-scoped), not `SET` (session-scoped). Combined with `pgbouncer` transaction-pooling this is safe — the tenant context dies with the transaction and the next user of the connection gets a clean slate.

For roles that need to cross tenants (admin tooling, batch jobs):

```sql
ALTER ROLE admin_app_user BYPASSRLS;
```

Audit every such role's access — they're the only credential that could cause a leak.

## Tenant context propagation

Tenant ID must flow through every layer. Wires get crossed at the layer boundaries — that's where bugs live.

| Layer | Mechanism |
|-------|-----------|
| HTTP | JWT claim (`tenant_id`) or path param (`/api/v1/restaurants/{tenant_id}/...`) |
| Event payloads | Required field on every event (`restaurant_id`) — see `schema-evolution.md` |
| Async / background tasks | Pass as explicit task arg; **never** inherit from "current" context |
| Logs / metrics / traces | Attached as a structured field on every log line and every span |
| Caches | Tenant-prefixed keys (`cache:tenant:<id>:...`) — see `caching-strategies.md` |

### FastAPI dependency pattern

```python
import structlog
from fastapi import Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

async def get_current_tenant(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    if not user.tenant_id:
        raise HTTPException(403, "missing_tenant")
    # Set on DB session so RLS auto-filters
    await db.execute(
        text("SET LOCAL app.current_tenant_id = :tid"),
        {"tid": str(user.tenant_id)},
    )
    # Bind to logger so every log line carries it
    structlog.contextvars.bind_contextvars(tenant_id=str(user.tenant_id))
    return user.tenant_id

@router.get("/outcomes")
async def list_outcomes(
    tenant_id: UUID = Depends(get_current_tenant),
    db:        AsyncSession = Depends(get_db),
):
    # RLS auto-filters; no explicit WHERE restaurant_id = ... needed
    return (await db.execute(select(RebookingOutcome))).scalars().all()
```

### Background tasks

Background tasks must receive the tenant ID as an argument, not inherit it from a contextvar that may belong to a previous request:

```python
async def handle_async(event: Event) -> None:
    await background_job.delay(
        event_id=event.event_id,
        tenant_id=str(event.restaurant_id),   # explicit; never implicit
    )

# Inside the worker
async def background_handler(event_id: str, tenant_id: str) -> None:
    structlog.contextvars.bind_contextvars(tenant_id=tenant_id)
    async with get_db() as session:
        await session.execute(text("SET LOCAL app.current_tenant_id = :tid"), {"tid": tenant_id})
        ...
```

## Per-tenant rate limiting

A noisy tenant must not exhaust shared rate-limit budgets. Use per-tenant counters:

```python
@router.get("/outcomes")
@limiter.limit("100/minute", key_func=lambda req: req.state.tenant_id)
async def list_outcomes(...): ...
```

See `rate-limiting.md` for the full pattern. The key function is the only difference between shared and per-tenant — same limiter, different key.

## Per-tenant quotas and budgets

Beyond per-minute rate limits, track and enforce longer-window per-tenant consumption:

- LLM token spend per tenant per month
- Event processing budget per tenant per day
- Storage quota (row count, byte count)

Implementation: a `tenant_usage` table updated on each operation, or a dedicated quota service. Enforce by reading the running total before the action and refusing if the budget is exceeded.

## Cross-tenant operations (admin only)

Some operations legitimately span tenants — billing reports, anomaly detection, support actions. Handle these explicitly:

- A dedicated admin role with the Postgres `BYPASSRLS` attribute.
- Explicit, named admin endpoints (no smuggling admin behaviour through tenant endpoints).
- Audit every admin action with a clear `cross_tenant=true` marker so security review can find them.

```sql
ALTER ROLE admin_app_user BYPASSRLS;
```

## Resource isolation beyond data

Data is the obvious axis; at scale, others matter too.

| Resource | Isolation pattern |
|----------|-------------------|
| Compute (CPU / memory) | Shared in app tier; per-tenant pods in dedicated workloads for noisy neighbours |
| Background jobs | Per-tenant queue, OR shared queue with priority + per-tenant rate caps |
| LLM provider context | Per-request basis; never include other tenants' data in prompts |
| Caches | Tenant-prefixed keys: `cache:tenant:<id>:...` |
| Search indexes | Separate index per tenant, OR tenant-filtered queries at the index level |
| Object storage | Path-prefixed (`s3://bucket/tenant-<id>/...`) with IAM policies enforcing the prefix |
| Metrics | Tenant label on every metric — but watch cardinality (see `prometheus-grafana.md`) |

## Per-tenant configuration

Tenants commonly need different settings: which features are enabled, default language / channel, retention policy, branding. Pattern:

```python
from pydantic import BaseModel

class TenantConfig(BaseModel):
    tenant_id: UUID
    features: dict[str, bool]
    notification_default_channel: str
    retention_days: int

async def get_tenant_config(tenant_id: UUID) -> TenantConfig:
    cached = await cache.get(f"tenant_config:{tenant_id}")
    if cached:
        return TenantConfig.model_validate_json(cached)
    config = await db.get_tenant_config(tenant_id)
    await cache.set(f"tenant_config:{tenant_id}", config.model_dump_json(), ex=60)
    return config
```

A feature-flag service is often the cleanest home for the boolean toggles — see `feature-flags.md` (PR-L, pending).

## Tenant lifecycle

| Action | What happens |
|--------|--------------|
| **Onboard** | Create tenant row, default config, default permissions, seed sample data, audit `tenant.created` |
| **Suspend** | Set status = `suspended`; RLS policy + app gate refuse new operations; data preserved |
| **Offboard** | Per GDPR / contract: anonymize → archive → hard-delete after retention window. Document every store; see `pii-gdpr.md` for the deletion fan-out shape |

Build these as explicit, audited endpoints — not ad-hoc DB scripts. Consistency matters.

## Cross-tenant access tests

Every multi-tenant service needs a test class that explicitly attempts cross-tenant access and asserts failure. This is the test that catches the next regression:

```python
async def test_cannot_read_other_tenants_outcome(
    client, tenant_a_token, tenant_b_outcome_id
):
    response = await client.get(
        f"/outcomes/{tenant_b_outcome_id}",
        headers={"Authorization": f"Bearer {tenant_a_token}"},
    )
    assert response.status_code == 404   # NOT 403 — don't reveal that the resource exists

async def test_cannot_write_into_another_tenant(client, tenant_a_token):
    response = await client.post(
        "/outcomes",
        headers={"Authorization": f"Bearer {tenant_a_token}"},
        json={"restaurant_id": str(OTHER_TENANT_ID), "...": "..."},
    )
    assert response.status_code in {403, 422}

async def test_cross_tenant_query_returns_empty(db_session):
    # With tenant A context, even a raw select on another tenant's row returns nothing
    await db_session.execute(text("SET LOCAL app.current_tenant_id = :a"), {"a": str(TENANT_A)})
    rows = await db_session.execute(
        select(RebookingOutcome).where(RebookingOutcome.id == TENANT_B_OUTCOME_ID)
    )
    assert rows.first() is None
```

Return `404` on cross-tenant read, not `403`. `403` confirms the resource exists, which is itself a leak.

## Pitfalls

- **Missing `tenant_id` WHERE clause** — the #1 cause of cross-tenant leaks. RLS removes this as a possibility.
- **Tenant context not bound to background tasks** — task inherits "default" or previous tenant; data crossed silently.
- **Shared cache keys** — `cache.get("user:123")` returns the wrong tenant's user.
- **Cross-tenant joins in admin tooling without filters** — operator sees combined data unintentionally.
- **JWT `tenant_id` not validated against resource `tenant_id`** — user with tenant A can access tenant B's resource if they guess (or scrape) the URL.
- **Log lines without `tenant_id`** — investigating an incident across tenants becomes a grep marathon.
- **Trace spans without `tenant_id`** — same; cross-tenant queries in the trace backend can't be filtered.
- **Single shared rate-limit bucket** — one noisy tenant DoSes everyone.
- **Cross-tenant data in LLM context** — RAG-style systems must filter retrieved chunks by tenant before they enter the prompt.

## Where used in repo

- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — `restaurant_id` on every row; per-restaurant rate caps; planned Postgres RLS adoption.
- All event-driven recipes — events carry `restaurant_id` (or equivalent tenant key) and propagate it through every handler.

## See also

- `rate-limiting.md` — per-tenant `key_func` for rate limiters.
- `caching-strategies.md` — tenant-prefixed cache keys.
- [audit-logging.md](./audit-logging.md) — `tenant_id` field on every audit event.
- [authorization-rbac.md](./authorization-rbac.md) — tenant-scoped permission checks (return 404 on cross-tenant).
- [pii-gdpr.md](./pii-gdpr.md) — deletion fan-out per tenant.
- `feature-flags.md` (PR-L, pending) — per-tenant feature toggles.
