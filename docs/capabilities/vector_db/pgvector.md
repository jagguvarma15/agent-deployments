---
id: vector_db.pgvector
kind: vector_db
provides: [embeddings_store]
env_vars: [DATABASE_URL]
docker: null
probe: postgres_select_one
bootstrap_step: bootstrap_vector_db
emit_files: []
docs: |
  pgvector extension on the existing Postgres instance. No new service —
  bootstrap step runs `CREATE EXTENSION IF NOT EXISTS vector;` plus optional
  table + ivfflat index.
---

# Capability: vector_db.pgvector

> Deep reference: [`stack/vector-qdrant.md`](../../stack/vector-qdrant.md) (swap section) and [`stack/relational-postgres.md`](../../stack/relational-postgres.md).

**Used for:** vector similarity search co-located with relational data, when total vector count is < ~5M.

## Why pick this

Zero extra services. If `relational.postgres` is already in the stack, this is the one-line addition that gives you vector retrieval without operating a second store. Trade-off: weaker p99 latency than Qdrant past a few million vectors, less expressive filtering DSL.

## Local setup

**No docker fragment.** This capability piggybacks on `relational.postgres`. The resolver enforces that `relational.postgres` is also present on the recipe; if not, generation fails with a clear error.

## Bootstrap (post docker_up + migrations)

`bootstrap_vector_db` runs (idempotently) against the Postgres `DATABASE_URL`:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
-- Per recipe-declared collections:
CREATE TABLE IF NOT EXISTS chunks (
    id          BIGSERIAL PRIMARY KEY,
    embedding   vector(1536),
    payload     JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

The table name + vector size + distance come from the recipe frontmatter `vector_collections:` block, defaulting to `chunks` / `1536` / `cosine`.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `DATABASE_URL` | *(inherited from relational.postgres)* | Postgres connection string |

## Cloud / production

Most managed Postgres providers (Neon, Supabase, Aiven, RDS) ship pgvector out of the box. Same connection string, same bootstrap SQL.

## When to swap it

- **→ `vector_db.qdrant`** past ~5M vectors, or when payload filtering becomes a hot path.

## See also

- `stack/vector-qdrant.md` — swap section
- `stack/relational-postgres.md` — host DB
