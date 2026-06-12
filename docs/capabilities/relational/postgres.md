---
id: relational.postgres
kind: relational
layer: infrastructure
provides: [relational_store, transactions, json_store]
env_vars: [DATABASE_URL, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB]
docker:
  service: postgres
  image: postgres:16-alpine
  ports: ["5432:5432"]
  volumes: ["postgres_data:/var/lib/postgresql/data"]
  environment:
    POSTGRES_USER: "${POSTGRES_USER:-agent}"
    POSTGRES_PASSWORD: "${POSTGRES_PASSWORD:-agent}"
    POSTGRES_DB: "${POSTGRES_DB:-agent_db}"
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-agent}"]
    interval: 5s
    timeout: 5s
    retries: 5
probe: postgres_select_one
bootstrap_step: null
provisioning_time: ~10s
cost_tier: free
est_tokens: 850
card:
  name: PostgreSQL
  description: "Postgres 16 with JSONB, transactions, and pgvector extension support."
  capabilities_provided: [relational_store, transactions, json_store, schema_evolution]
  required_credentials: []
emit_files: []
docs: |
  Postgres 16 for conversation state, domain data, LangGraph checkpointing,
  and Langfuse backend storage. Migrations run via the project's `migrations`
  step (Alembic in Python, Drizzle Kit in TypeScript).
tags: [relational, sql, self-hosted]
when_to_load: "recipe declares relational.postgres"
---

# Capability: relational.postgres

> Deep reference: [`stack/relational-postgres.md`](../../stack/relational-postgres.md). This page is the provisioning contract.

**Used for:** conversation state, document metadata, LangGraph checkpoints, Langfuse backend.

## Local setup

The docker fragment above is merged into `docker-compose.yml`. `pg_isready` probe runs on the container. Connect locally with `psql postgresql://agent:agent@localhost:5432/agent_db`.

## Bootstrap

None at the capability level — the project's `migrations` step takes over once the container is healthy. The Python track runs `alembic upgrade head`; the TypeScript track runs `drizzle-kit migrate`. Migration files come from the generated project's `migrations/` directory.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://agent:agent@localhost:5432/agent_db` | SQLAlchemy connection string (Python) |
| `POSTGRES_USER` | `agent` | DB user |
| `POSTGRES_PASSWORD` | `agent` | DB password (override in prod via secrets) |
| `POSTGRES_DB` | `agent_db` | DB name |

The TypeScript track expects `DATABASE_URL` in the `postgres://` shape (no `+asyncpg` driver suffix); the resolver emits both shapes into `.env.example`.

## Client integration

**Python (asyncpg via SQLAlchemy 2.0):**

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async with SessionLocal() as session:
    result = await session.execute(text("SELECT 1"))
    print(result.scalar())
```

**TypeScript (postgres.js):**

```ts
import postgres from "postgres";
const sql = postgres(process.env.DATABASE_URL!, { max: 10 });

const rows = await sql`SELECT 1 AS one`;
console.log(rows[0].one);
```

## Cloud / production

- **Managed** — Neon, Supabase, Aiven, RDS, Cloud SQL. Set `DATABASE_URL` to the cluster endpoint.
- **Self-hosted** — pgBouncer ([`stack/connection-pooling-pgbouncer.md`](../../stack/connection-pooling-pgbouncer.md)) in front of the cluster; replication via streaming or logical depending on failover requirements.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `connection refused 5432` | Container not up yet | `docker compose logs postgres` — wait for "ready to accept connections" |
| `password authentication failed` | Stale volume with different credentials | `docker compose down -v` to drop the volume; re-bring-up applies env defaults |
| `extension "vector" does not exist` | pgvector capability not enabled | Add `vector_db.pgvector` to the recipe or run `CREATE EXTENSION vector` manually |
| Slow query inside compose | Cold buffer cache after restart | First query is slow; subsequent calls land in buffer cache. Verify with `EXPLAIN ANALYZE` |

## See also

- [`stack/relational-postgres.md`](../../stack/relational-postgres.md) — full reference + integration code
- [`stack/connection-pooling-pgbouncer.md`](../../stack/connection-pooling-pgbouncer.md) — production pooling
- [`capabilities/vector_db/pgvector.md`](../vector_db/pgvector.md) — vector retrieval on this DB
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
