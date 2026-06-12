---
tags: [database, connection-pooling]
when_to_load: "recipe declares relational.postgres and high concurrency"
---

# Stack pick: PgBouncer (connection pooling)

**Choice:** PgBouncer in transaction-pooling mode for Postgres-backed services
**Used for:** Bounding the connection footprint to Postgres when running many app instances or high-concurrency async workers

## Why this over alternatives

| Option | Verdict |
|--------|---------|
| Direct Postgres connections | Each connection ≈ 10 MB Postgres memory + a backend process; doesn't scale past a few hundred |
| App-level pool only (SQLAlchemy pool / `pg` pool) | Per-process pool; N processes × pool size = total connections; quickly exceeds Postgres `max_connections` |
| PgBouncer | Single shared pool in front of Postgres; thousands of client connections → tens of server connections |
| pgcat | Newer, Rust-based; sharding-aware; less battle-tested |
| RDS Proxy / Cloud SQL Auth Proxy | Managed; AWS / GCP-specific; convenient when single-cloud |

For mise: **PgBouncer in transaction mode** is the default for any Postgres-backed service at scale.

## Pooling modes

| Mode | Pros | Cons |
|------|------|------|
| **Session** | Full Postgres feature compatibility | One server connection per client connection — no real pooling benefit |
| **Transaction** | Real pooling; high concurrency | No cross-statement `SET`, no `LISTEN/NOTIFY`, no client-side prepared statements |
| **Statement** | Most aggressive | Almost no feature compatibility; rarely useful |

**Default: transaction mode.** Most app code works with the caveats below.

## Caveats of transaction mode

- **`SET LOCAL` only persists within a transaction.** Fine for tenant context — wrap requests in `BEGIN ... COMMIT` (typical of any ORM unit of work). See [multi-tenancy.md](../cross-cutting/multi-tenancy.md) for the RLS pattern.
- **Prepared statements.** Client-side prepared statements break (different server connections between prepare + execute). Use server-side prepared via the Postgres extended protocol (asyncpg + Postgres 14+ + `server_reset_query` left empty); or disable client prepares (SQLAlchemy `execution_options(no_parameters=True)` or driver-specific flag).
- **Session-scoped advisory locks** don't survive transaction end. Use transaction-scoped variants: `pg_try_advisory_xact_lock(...)`.
- **`LISTEN/NOTIFY`** doesn't work through transaction pooling. Run a separate **session-mode** PgBouncer pool (or direct connection) for any LISTEN-using subscriber.
- **Temporary tables.** Session-scoped temp tables don't survive transaction end; use `ON COMMIT DROP` or schema-qualified persistent staging tables.

## docker-compose setup

```yaml
pgbouncer:
  image: edoburu/pgbouncer:latest
  environment:
    DB_HOST: postgres
    DB_PORT: 5432
    DB_USER: agent
    DB_PASSWORD: agent
    DB_NAME: agent_db
    POOL_MODE: transaction
    MAX_CLIENT_CONN: 1000
    DEFAULT_POOL_SIZE: 25
    RESERVE_POOL_SIZE: 5
    SERVER_RESET_QUERY: DISCARD ALL
    AUTH_TYPE: scram-sha-256
  ports:
    - "6432:6432"
  depends_on:
    postgres:
      condition: service_healthy
```

App connects to `postgres://agent:agent@pgbouncer:6432/agent_db` instead of straight to Postgres. Nothing else in the app changes.

## Application-side pool configuration

With PgBouncer in transaction mode, the app-level pool should be tiny — PgBouncer is the real pool.

### SQLAlchemy + asyncpg

```python
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

# PgBouncer in transaction mode → use NullPool app-side. Every checkout opens a
# fresh client connection; PgBouncer multiplexes to a small server pool.
engine = create_async_engine(
    "postgresql+asyncpg://agent:agent@pgbouncer:6432/agent_db",
    poolclass=NullPool,
    connect_args={
        "statement_cache_size": 0,         # disable asyncpg's prepared-statement cache
        "prepared_statement_cache_size": 0,
    },
)
```

Alternative: a small app pool (5–10 per process) if you have short-lived per-connection state that benefits from reuse. Above 10 per process is usually a sign you've under-sized PgBouncer's server pool.

### Node / `pg`

```typescript
import { Pool } from "pg";

export const pool = new Pool({
  connectionString: "postgres://agent:agent@pgbouncer:6432/agent_db",
  max: 5,                                   // small; PgBouncer is the real pool
  idleTimeoutMillis: 30_000,
  statement_timeout: 30_000,
});
```

## Sizing

| Parameter | Rule of thumb |
|-----------|---------------|
| `DEFAULT_POOL_SIZE` (server connections per pool) | `(Postgres max_connections − overhead) / N_databases` |
| `MAX_CLIENT_CONN` (total clients PgBouncer accepts) | Aggregate across all app instances; 1 000 – 10 000 typical |
| `RESERVE_POOL_SIZE` | 5–10 % of pool size; burst capacity |
| Postgres `max_connections` | 100–200 for managed RDS-class; 500–1 000 for bigger instances |

A worked example: a Postgres with `max_connections=200`, three databases, ~20 connection overhead for replication / monitoring. → `DEFAULT_POOL_SIZE = (200 − 20) / 3 ≈ 60`. With 20 app pods each holding up to 100 client connections, `MAX_CLIENT_CONN = 2 000`.

## Monitoring

PgBouncer exposes a stats DB on the same port:

```bash
psql -h pgbouncer -p 6432 -U pgbouncer -d pgbouncer -c "SHOW STATS"
psql -h pgbouncer -p 6432 -U pgbouncer -d pgbouncer -c "SHOW POOLS"
psql -h pgbouncer -p 6432 -U pgbouncer -d pgbouncer -c "SHOW CLIENTS"
```

Export to Prometheus via `pgbouncer_exporter`. Key metrics:

- `pgbouncer_clients_waiting` — sustained > 0 means the server pool is too small.
- `pgbouncer_server_active` / `pgbouncer_server_idle` — saturation indicator.
- `pgbouncer_avg_query_time` — latency added by the pool itself.

Alert when waiting clients > 0 for > 1 min, or server pool > 90% utilization sustained.

## Pitfalls

- **Transaction mode + per-session settings** (`SET search_path = ...`) — settings are lost on next checkout. Use `SET LOCAL` inside a transaction, or move the config into `default_transaction_*` server-side.
- **App pool sized for direct Postgres** — connection storm on PgBouncer. With PgBouncer, app pool should be small (often `NullPool`).
- **Forgetting `SERVER_RESET_QUERY`** — state leaks between clients (cursors, temp tables, set settings).
- **Single PgBouncer instance** — SPOF; run 2+ behind a TCP load balancer for HA.
- **Not exporting metrics** — pool saturation only noticed when query latency spikes.
- **Client-side prepared statements left on** — break under transaction pooling; "statement does not exist" errors at random.
- **`MAX_CLIENT_CONN` smaller than peak app connection demand** — apps get "connection refused" from PgBouncer.

## Where used in repo

- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — kicks in when deployed with multiple worker replicas at scale.
- Any recipe using [Postgres](./relational-postgres.md) once concurrency exceeds ~50 simultaneous queries.

## Production considerations

- **HA** — 2+ PgBouncer instances behind a TCP load balancer (HAProxy, AWS NLB, GCP TCP LB). Health-check on a connection to the stats DB.
- **TLS to backend** — `server_tls_sslmode=require`; pair with `auth_type=scram-sha-256` for client auth, or `auth_type=cert` for mTLS.
- **Threading** — PgBouncer is single-threaded per process. For high QPS, run multiple processes on the same host with `so_reuseport`, or scale horizontally behind the LB.
- **Version match** — pin PgBouncer version in the deploy; protocol-level bugs do happen at the boundary with new Postgres major versions.

## See also

- `relational-postgres.md` — Postgres itself; PgBouncer sits in front.
- `cross-cutting/multi-tenancy.md` — `SET LOCAL app.current_tenant_id` is transaction-scoped, which is exactly what transaction-mode PgBouncer wants.
- `cross-cutting/health-graceful-shutdown.md` — readiness should fail if PgBouncer is unreachable.
- `prometheus-grafana.md` — `pgbouncer_exporter` metrics surface.
