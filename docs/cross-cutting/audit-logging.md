# Cross-cutting: Audit logging

**Concern:** A separate, immutable trail of who did what, when, and to what — for compliance, incident investigation, and trust.
**Library:** Postgres `audit_events` table + triggers; archive to S3 / Glacier for long retention.
**Lives in:** Inline below — every mutating admin action and every PII read writes an audit event.

## What it provides

- A clear separation between **audit log** (compliance / forensics) and **application log** (debugging).
- A canonical schema with `who / what / when / why / where`.
- Storage options with their tradeoffs (Postgres table, append-only files, dedicated audit stores, SIEM).
- A tamper-evidence ladder — append-only constraints → hash chain → cryptographic signing.

## Audit log vs application log

| | Audit log | Application log |
|---|-----------|-----------------|
| **Retention** | Years (driven by compliance) | Days to weeks |
| **Mutability** | Append-only, immutable | Mutable, rotated, sometimes redacted post-hoc |
| **Schema** | Strict, versioned, stable | Loose; evolves with the code |
| **Tamper evidence** | Required (constraints, hash chain, signing) | Best-effort |
| **Driver** | Compliance, legal, incident review | Debugging, on-call, dashboards |
| **PII handling** | Identifiers + hashes only, never values | Sometimes scrubbed, often messy |
| **Loss tolerance** | None — durability matters more than latency | OK to drop on overload |

**Don't try to make application logs serve as audit logs.** Different goals, different consumers, different retention, different durability requirements. Cheap to keep separate; expensive to merge after a compliance review asks for one.

## What to capture

For every audit event:

- **Who** — `actor_type` (user / service / system), `actor_id`, `tenant_id`, `ip`, `user_agent`
- **What** — `action` (enum, e.g. `rebooking.replay`), `resource_type`, `resource_id`, `before` / `after` for mutations
- **When** — UTC timestamp with millisecond precision
- **Why** — `request_id`, `trace_id`, optional `justification` for high-stakes / sensitive reads
- **Where** — `service`, `env`, `instance_id`

The five-W shape is non-negotiable. Compliance and incident investigators ask exactly these questions.

## Schema example

```python
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel

class AuditEvent(BaseModel):
    event_id: UUID
    timestamp: datetime
    actor_type: Literal["user", "service", "system"]
    actor_id: str
    tenant_id: str | None
    action: str                          # "rebooking.replay", "customer.pii_read"
    resource_type: str                   # "rebooking_outcome", "customer"
    resource_id: str
    before: dict | None = None           # null for reads
    after: dict | None = None            # null for reads or deletes
    request_id: str
    trace_id: str
    ip: str | None = None
    user_agent: str | None = None
    justification: str | None = None
    service: str
    env: str
    schema_version: int = 1
```

```sql
CREATE TABLE audit_events (
    event_id        UUID        PRIMARY KEY,
    timestamp       TIMESTAMPTZ NOT NULL,
    actor_type      TEXT        NOT NULL CHECK (actor_type IN ('user','service','system')),
    actor_id        TEXT        NOT NULL,
    tenant_id       TEXT,
    action          TEXT        NOT NULL,
    resource_type   TEXT        NOT NULL,
    resource_id     TEXT        NOT NULL,
    before          JSONB,
    after           JSONB,
    request_id      TEXT        NOT NULL,
    trace_id        TEXT        NOT NULL,
    ip              INET,
    user_agent      TEXT,
    justification   TEXT,
    service         TEXT        NOT NULL,
    env             TEXT        NOT NULL,
    schema_version  INT         NOT NULL DEFAULT 1,
    prev_hash       BYTEA,                              -- for hash chain (optional)
    row_hash        BYTEA                               -- for hash chain (optional)
);

CREATE INDEX audit_events_actor_idx    ON audit_events (actor_id, timestamp DESC);
CREATE INDEX audit_events_resource_idx ON audit_events (resource_type, resource_id, timestamp DESC);
CREATE INDEX audit_events_tenant_idx   ON audit_events (tenant_id, timestamp DESC);
```

## Storage options

| Backend | Pros | Cons | Fit |
|---------|------|------|-----|
| Postgres `audit_events` table | Easy to query, transactional with the action | Mutable unless you add append-only triggers | Default for most workloads |
| Append-only file → S3 + Glacier | Cheap, immutable, long retention | Hard to query without a separate index | Long-term archive + secondary store |
| Dedicated audit DB (Vault audit device, AWS CloudTrail) | Purpose-built, immutable by design | Extra infra; integration cost | Regulated environments |
| SIEM (Splunk, Datadog) | Integrated alerting, retention | Cost, vendor lock-in | When you already have one |

**Sensible default for mise / rebooking:** Postgres `audit_events` with append-only triggers, plus a nightly job that ships closed days to S3 with Object Lock for long-term retention.

## Tamper evidence

Three levels; pick by your regulatory ceiling.

### Level 1 — append-only constraints

Postgres triggers that block `UPDATE` and `DELETE` on the audit table:

```sql
CREATE OR REPLACE FUNCTION audit_no_mutate() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_events_no_update
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_no_mutate();
```

Also revoke `UPDATE` / `DELETE` from the application role:

```sql
REVOKE UPDATE, DELETE ON audit_events FROM app_role;
GRANT  INSERT, SELECT ON audit_events TO app_role;
```

Caveat: a `superuser` can disable triggers. Don't run the app as superuser.

### Level 2 — hash chain

Each row stores `prev_hash` (the row hash of the previous event) and `row_hash` (of itself, including the prev hash). Tampering with any row breaks the chain from that point forward.

```python
def compute_row_hash(prev_hash: bytes, event: AuditEvent) -> bytes:
    payload = event.model_dump_json(exclude={"prev_hash", "row_hash"}).encode()
    return hashlib.sha256(prev_hash + payload).digest()
```

Run a verification job daily: walk the chain, recompute, alert on mismatch.

### Level 3 — cryptographic signing

Each entry signed by a key the application doesn't hold (HSM, KMS). The application asks the signer service for a signature on each row. Tampering is detectable even if the DB is fully compromised.

Use level 3 for regulated industries (finance, healthcare). Levels 1 + 2 are enough for most teams.

## Retention

| Category | Retention | Notes |
|----------|-----------|-------|
| Operational events (admin action, replay, DLQ purge) | 90 days hot, 1 year cold | Sufficient for typical incident review |
| Authz changes (role grants, permission edits) | 2 years | Compliance reviews tend to look at policy evolution |
| Sensitive actions (refunds, customer deletion) | 7 years | Tax / regulatory windows |
| PII access logs | 6 years | GDPR / data-protection accountability |

Document your retention matrix in `docs/operations/audit-retention.md` (or equivalent). Have a job that prunes per the matrix; alert when the prune fails.

## What NOT to log

- **Passwords, JWT contents, raw secrets.** Even in error paths.
- **Full PII field values.** Store the identifier + a hash; resolve to the value only at display time. See `pii-gdpr.md`.
- **Request bodies.** They may contain user-uploaded content, PII, or secrets.
- **Anything that hasn't passed the input validator** — log validated, typed values, not raw input.

## Implementation pattern

```python
from contextvars import ContextVar

current_ctx: ContextVar["Context"] = ContextVar("audit_ctx")

class Context(BaseModel):
    request_id: str
    trace_id: str
    actor: "Actor"
    tenant_id: str | None

async def audit(
    action: str,
    resource_type: str,
    resource_id: str,
    *,
    before: dict | None = None,
    after: dict | None = None,
    justification: str | None = None,
) -> None:
    ctx = current_ctx.get()
    event = AuditEvent(
        event_id=uuid4(),
        timestamp=datetime.now(tz=UTC),
        actor_type=ctx.actor.type,
        actor_id=ctx.actor.id,
        tenant_id=ctx.tenant_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before=before,
        after=after,
        request_id=ctx.request_id,
        trace_id=ctx.trace_id,
        justification=justification,
        service=settings.service_name,
        env=settings.env,
    )
    await db.execute(INSERT_AUDIT_SQL, event.model_dump())
```

Wrap the side-effecting action and the audit write in a single transaction where possible — guarantees either both happen or neither. For systems where that's not possible (separate DB), accept at-least-once audit writes and dedupe on `event_id`.

### Logging denied attempts

Failed permission checks and authn failures also belong in the audit log — they're the evidence trail for probing and brute-force attempts.

```python
try:
    require_permission(Permission.rebooking_replay)(user)
except HTTPException:
    await audit("authz.denied", "endpoint", "/admin/replay",
                justification=f"missing permission rebooking_replay")
    raise
```

## Tests

- **Schema test** — every required field present; `schema_version` increments only via migration.
- **Append-only test** — `UPDATE` and `DELETE` against `audit_events` raise.
- **Hash-chain test** — flip a byte in row N, run verifier, assert detected at row N.
- **PII-not-logged test** — call `audit(...)` with PII-bearing input; assert PII fields are not present in the resulting row.
- **Transaction-atomicity test** — make the audit write fail; assert the side-effecting action also rolled back.

## Pitfalls

- **Audit log in the same DB as app data with no append-only constraint** — tampering possible by the same code paths that write data.
- **Logging PII in `before` / `after`** — defeats the purpose of PII protection. Diff identifiers, not values.
- **No `tenant_id`** — can't reconstruct per-tenant history; can't satisfy per-tenant data export.
- **Async fire-and-forget without delivery guarantee** — audit gaps under load. Use a durable queue or transactional write.
- **Audit only the success path** — denied attempts are exactly the signal you need for security review.
- **Truncating long fields silently** — store the full payload or store a hash + pointer, never silently truncate.
- **Same `request_id` reused across retries** — fix the propagation; without distinct request ids, retries look like one action.

## Where used in repo

- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — `/admin/replay`, `/admin/dlq/*` and any PII read write to `audit_events`.

## See also

- [authorization-rbac.md](./authorization-rbac.md) — denied permission checks should audit.
- [pii-gdpr.md](./pii-gdpr.md) — PII reads must audit; PII values must not be in the audit row.
- [auth-jwt.md](./auth-jwt.md) — login success / failure events.
