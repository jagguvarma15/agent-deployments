---
id: vector_db.pgvector
kind: vector_db
implements:
  port: vector_db
  interface_version: "1.0"
layer: data
requires: [relational.postgres]
bootstrap_inputs:
  vector_extension: vector
  default_table_name: chunks
  default_vector_size: 1536
provides: [embeddings_store]
env_vars: [DATABASE_URL]
docker: null
probe: postgres_select_one
bootstrap_step: bootstrap_vector_db
provisioning_time: ~5s
cost_tier: free
est_tokens: 600
card:
  name: pgvector
  description: "Postgres extension adding a `vector` data type with cosine/euclidean/dot-product distance operators."
  capabilities_provided: [vector_search, sql_join_on_vectors]
  required_credentials: []
emit_files: []
docs: |
  pgvector extension on the existing Postgres instance. No new service —
  bootstrap step runs `CREATE EXTENSION IF NOT EXISTS vector;` plus
  optional table + ivfflat index.
tags: [vector-search, retrieval, postgres-native]
when_to_load: "recipe declares vector_db.pgvector"
stack_docs:
  - stack/relational-postgres.md
  - stack/vector-qdrant.md
---

# Capability: vector_db.pgvector

> Deep reference: [`stack/vector-qdrant.md`](../../stack/vector-qdrant.md) (swap section) and [`stack/relational-postgres.md`](../../stack/relational-postgres.md).

**Used for:** vector similarity search co-located with relational data on the same Postgres instance.

## Local setup

**No docker fragment.** This capability piggybacks on `relational.postgres`. The catalog resolver enforces that `relational.postgres` is on the recipe.

## Bootstrap (post docker_up + migrations)

`bootstrap_vector_db` runs (idempotently) against the Postgres `DATABASE_URL`:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

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

Table name + vector size + distance come from the recipe's `vector_collections:` block, defaulting to `chunks` / `1536` / `cosine`.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `DATABASE_URL` | *(inherited from `relational.postgres`)* | Postgres connection string |

## Client integration

**Python (SQLAlchemy + pgvector):**

```python
from sqlalchemy import select, text
from pgvector.sqlalchemy import Vector

class Chunk(Base):
    __tablename__ = "chunks"
    id = mapped_column(BigInteger, primary_key=True)
    embedding = mapped_column(Vector(1536))
    payload = mapped_column(JSONB)

async with SessionLocal() as session:
    session.add(Chunk(embedding=embedding, payload={"source": "guide.md"}))
    await session.commit()

    hits = await session.execute(
        select(Chunk).order_by(Chunk.embedding.cosine_distance(query_embedding)).limit(5)
    )
```

**TypeScript (postgres.js + pgvector-node):**

```ts
import postgres from "postgres";
import pgvector from "pgvector/utils";

const sql = postgres(process.env.DATABASE_URL!);

await sql`INSERT INTO chunks (embedding, payload) VALUES (${pgvector.toSql(embedding)}, ${{ source: "guide.md" }})`;

const hits = await sql`
  SELECT id, payload
  FROM chunks
  ORDER BY embedding <=> ${pgvector.toSql(queryEmbedding)}
  LIMIT 5
`;
```

## Cloud / production

Most managed Postgres providers (Neon, Supabase, Aiven, RDS) ship pgvector out of the box. Same connection string, same bootstrap SQL.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `extension "vector" does not exist` | Postgres image lacks the extension | Switch to `pgvector/pgvector:pg16` image in the relational.postgres capability, or install the extension via the platform UI for managed Postgres |
| `function vector_cosine_ops does not exist` | Older pgvector version | Bump pgvector to `>=0.5.0`; check with `SELECT extversion FROM pg_extension WHERE extname='vector'` |
| Slow vector search at 1M+ rows | ivfflat lists tuned for smaller datasets | Recreate the index with `lists = sqrt(rows)`; consider HNSW (pgvector >=0.5) |
| Index size much larger than data | HNSW build with low recall | Lower `m` and `ef_construction`; trade recall for index size |

## See also

- [`stack/vector-qdrant.md`](../../stack/vector-qdrant.md) — swap section
- [`stack/relational-postgres.md`](../../stack/relational-postgres.md) — host DB
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
