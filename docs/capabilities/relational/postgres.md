---
id: relational.postgres
kind: relational
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
emit_files: []
docs: |
  Postgres 16 for conversation state, domain data, LangGraph checkpointing,
  Langfuse backend. Migrations run via the existing `migrations` step (Alembic
  in Python, Drizzle Kit in TypeScript).
---

# Capability: relational.postgres

> Deep reference: [`stack/relational-postgres.md`](../../stack/relational-postgres.md). This page is the provisioning contract.

**Used for:** conversation state, document metadata, LangGraph checkpoints, Langfuse backend. The default relational store.

## Why pick this

Postgres is the answer for any agent that needs durable structured state. JSON support is excellent, pgvector extension brings vector retrieval, and LangGraph checkpointing was designed for it. The `relational.postgres` capability covers the container; the existing `migrations` step handles schema evolution.

## Local setup

The docker fragment above is merged into `docker-compose.yml`. `pg_isready` probe runs on the container. Connect locally: `psql postgresql://agent:agent@localhost:5432/agent_db`.

## Bootstrap

None at the capability level — the existing `migrations` orchestrator step takes over once the container is healthy. The Python track runs `alembic upgrade head`; the TypeScript track runs `drizzle-kit migrate`. Migration files come from the generated project's `migrations/` directory.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://agent:agent@localhost:5432/agent_db` | SQLAlchemy connection string (Python) |
| `POSTGRES_USER` | `agent` | DB user |
| `POSTGRES_PASSWORD` | `agent` | DB password (override in prod via secrets) |
| `POSTGRES_DB` | `agent_db` | DB name |

The TypeScript track expects `DATABASE_URL` in the `postgres://` shape (no `+asyncpg` driver suffix); the resolver emits both shapes into `.env.example`.

## Cloud / production

- **Managed** — Neon, Supabase, Aiven, RDS, Cloud SQL. Set `DATABASE_URL` to the cluster endpoint. No code changes.
- **Self-hosted production** — pgBouncer (`stack/connection-pooling-pgbouncer.md`) in front of the cluster; replication via streaming or logical depending on failover requirements.

## When to swap it

You don't. Postgres is the canonical relational pick. If you find yourself wanting MongoDB, the right move is usually a JSONB column on Postgres.

## See also

- `stack/relational-postgres.md` — full reference, integration code, alternatives matrix
- `stack/connection-pooling-pgbouncer.md` — production pooling
- `capabilities/vector_db/pgvector.md` — piggyback vector retrieval on this DB
