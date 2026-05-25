# Postgres

> Relational database. Used for conversation state, document metadata, LangGraph checkpointing, and (with `pgvector`) embeddings.

**Signup**: not required for local Docker; hosted options below.

## Quick install (local Docker)

```bash
docker run -d --name postgres \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=agent_db \
  postgres:16-alpine
```

Stop / restart later:

```bash
docker stop postgres && docker start postgres
```

## Hosted alternatives

| Provider | Free tier | Quickstart |
|----------|-----------|------------|
| Neon | 0.5 GB, branching | https://neon.tech/docs/get-started-with-neon |
| Supabase | 500 MB, auth + storage included | https://supabase.com/docs/guides/database |
| Render | 256 MB, single instance | https://render.com/docs/databases |
| AWS RDS | none (free tier eligible for first year) | https://docs.aws.amazon.com/rds/ |

Hosted Postgres usually requires `?sslmode=require` appended to the connection string.

## Verify

```bash
psql "$DATABASE_URL" -c "select version();"
```

If `psql` is not installed: `docker exec postgres pg_isready -U postgres`.

## Wire into your project

Set in `.env.local`:

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/agent_db
```

For SQLAlchemy + async drivers: `postgresql+asyncpg://...`. For `pgvector`: install the extension once after the DB exists — `CREATE EXTENSION IF NOT EXISTS vector;`.

## Migrations

Most recipes use Alembic for Python:

```bash
uv run alembic upgrade head
```

Generate a new migration from model changes:

```bash
uv run alembic revision --autogenerate -m "add reservation table"
```

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `role "postgres" does not exist` | Connection string uses a different user than the container | Match `POSTGRES_USER` and the URL's user component |
| `database "agent_db" does not exist` | Container started without `POSTGRES_DB` set | `docker exec postgres createdb -U postgres agent_db` |
| `SSL connection required` | Hosted provider enforces TLS | Append `?sslmode=require` to `DATABASE_URL` |
| `Too many connections` | App opens connections without pooling | Add PgBouncer (see stack doc) or lower app-side pool size |

## See also

- [`docs/stack/relational-postgres.md`](../stack/relational-postgres.md) — full schema, indexing, partitioning guidance
- [`docs/stack/connection-pooling-pgbouncer.md`](../stack/connection-pooling-pgbouncer.md) — when you outgrow direct connections
