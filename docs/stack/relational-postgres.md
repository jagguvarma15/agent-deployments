# Stack pick: Postgres

**Choice:** Postgres 16-alpine, self-hosted via Docker
**Used for:** Conversation state, document metadata, Langfuse backend, LangGraph checkpointing

## Why this over alternatives

| Option | Why not |
|--------|---------|
| MySQL | Postgres has better JSON support, pgvector extension, and is the standard for LangGraph checkpointing |
| SQLite | Single-writer, no concurrent access for multi-container setups |
| MongoDB | Unnecessary for the structured data these agents produce |
| DynamoDB | Managed-only, vendor lock-in, can't run offline |

## Local setup

Defined in `common/docker-compose.base.yml`:

```yaml
postgres:
  image: postgres:16-alpine
  environment:
    POSTGRES_USER: ${POSTGRES_USER:-agent}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-agent}
    POSTGRES_DB: ${POSTGRES_DB:-agent_db}
  ports:
    - "${POSTGRES_PORT:-5432}:5432"
  volumes:
    - postgres_data:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-agent}"]
    interval: 5s
    timeout: 5s
    retries: 5
```

Connect locally: `psql postgresql://agent:agent@localhost:5432/agent_db`

## Config knobs that matter

| Knob | Default | Effect |
|------|---------|--------|
| `POSTGRES_USER` | `agent` | Database user |
| `POSTGRES_PASSWORD` | `agent` | Database password |
| `POSTGRES_DB` | `agent_db` | Database name |
| `POSTGRES_PORT` | `5432` | Host port mapping |
| `DATABASE_URL` | `postgresql+asyncpg://agent:agent@localhost:5432/agent_db` | SQLAlchemy connection string |

## Integration pattern

### Python (SQLAlchemy + asyncpg)

```python
# app/db/session.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine = create_async_engine(settings.database_url, echo=settings.app_env == "development")
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
```

```python
# app/db/models.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    content_hash = Column(String, nullable=False)
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

### TypeScript (Drizzle ORM)

```typescript
import { drizzle } from "drizzle-orm/node-postgres";
import { pgTable, text, integer, timestamp } from "drizzle-orm/pg-core";

export const documents = pgTable("documents", {
  id: text("id").primaryKey(),
  title: text("title").notNull(),
  contentHash: text("content_hash").notNull(),
  chunkCount: integer("chunk_count").default(0),
  createdAt: timestamp("created_at").defaultNow(),
});

const db = drizzle(process.env.DATABASE_URL!);
```

## Migrations

- **Python:** Alembic (`alembic revision --autogenerate`, `alembic upgrade head`)
- **TypeScript:** Drizzle Kit (`drizzle-kit generate`, `drizzle-kit migrate`)

In dev, tables are auto-created via `Base.metadata.create_all()` in the FastAPI lifespan. Use migrations in production.

## Where used in repo

- **Every prototype** -- conversation state and domain-specific data
- **`docs-rag-qa`** -- `documents` and `chunks` tables
- **Langfuse** -- uses a dedicated database on the same Postgres instance (`langfuse` DB)
- **LangGraph checkpointing** -- stores graph state for resume/replay

## Swapping to pgvector

Add the vector extension to the existing Postgres instance (no new service needed):

```sql
CREATE EXTENSION vector;
ALTER TABLE chunks ADD COLUMN embedding vector(1536);
CREATE INDEX ON chunks USING ivfflat (embedding vector_cosine_ops);
```

This replaces Qdrant for simple use cases (< 5M vectors). See [stack/vector-qdrant.md](vector-qdrant.md) for the trade-off analysis.
