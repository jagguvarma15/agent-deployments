# Playbook: Stack Swaps

Every blueprint uses the same canonical stack. You don't have to. This guide shows how to swap any component for an alternative — and what changes when you do.

---

## Swap reference

| Slot | Default | Alternative | Swap scope | What changes |
|------|---------|-------------|------------|--------------|
| LLM | Claude (Sonnet 4.6) | OpenAI GPT-4.1 | 1-line | Provider import |
| LLM | Claude (Sonnet 4.6) | Local via Ollama | Config | Base URL + model name |
| Agent framework (Py) | Pydantic AI | LangGraph | Multi-file | Agent definition + tool wiring |
| Agent framework (Py) | LangGraph | Pydantic AI | Multi-file | Graph → agent + tools |
| Agent framework (TS) | Vercel AI SDK | Mastra | Multi-file | Agent definition + workflow |
| API layer (Py) | FastAPI | Litestar | Multi-file | main.py + routes + auth dependency |
| API layer (TS) | Hono | Express | Multi-file | Server setup + middleware |
| Vector DB | Qdrant | Pinecone | 1-file | Retriever module |
| Vector DB | Qdrant | pgvector | 1-file | Use Postgres extension, drop Qdrant container |
| Relational DB | Postgres 16 | SQLite | Config | Connection string (dev/prototype only) |
| Cache | Redis 7 | In-memory | 1-file | Rate limiter backend (not distributed) |
| Tracing | Langfuse | LangSmith | 1-file | Observability setup module |
| Tracing | Langfuse | None (skip) | Delete | Remove tracing calls + container |
| Eval | DeepEval + RAGAS | Promptfoo only | Config | Simpler eval pipeline, less metric coverage |

---

## Swap details

### LLM: Claude → OpenAI

**Scope:** 1-line change per file that creates a model/provider.

**Python (Pydantic AI):**
```python
# Before
from pydantic_ai import Agent
agent = Agent("claude-sonnet-4-6-20250514", ...)

# After
agent = Agent("openai:gpt-4.1", ...)
```

**TypeScript (Vercel AI SDK):**
```typescript
// Before
import { anthropic } from "@ai-sdk/anthropic";
const model = anthropic("claude-sonnet-4-6-20250514");

// After
import { openai } from "@ai-sdk/openai";
const model = openai("gpt-4.1");
```

**Env change:** Replace `ANTHROPIC_API_KEY` with `OPENAI_API_KEY`.

---

### LLM: Claude → Local (Ollama)

**Scope:** Config change — point at a local Ollama instance.

**Python (Pydantic AI):**
```python
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

model = OpenAIModel("llama3.1", base_url="http://localhost:11434/v1")
agent = Agent(model, ...)
```

**TypeScript (Vercel AI SDK):**
```typescript
import { createOpenAI } from "@ai-sdk/openai";
const ollama = createOpenAI({ baseURL: "http://localhost:11434/v1" });
const model = ollama("llama3.1");
```

**Trade-off:** No API key needed, but tool use and structured output quality varies by model. Test thoroughly.

---

### API layer: FastAPI → Litestar

**Scope:** Multi-file — main.py, all route files, auth dependency.

1. Replace `FastAPI()` with `Litestar(route_handlers=[...])`.
2. Replace `APIRouter` with Litestar controllers.
3. Replace `Depends()` with Litestar's dependency injection.
4. Keep Pydantic models as-is (Litestar supports them natively).

See [`docs/stack/api-fastapi.md`](../stack/api-fastapi.md) § "Swapping to Litestar" for the detailed migration.

---

### API layer: Hono → Express

**Scope:** Multi-file — server setup, middleware, route definitions.

1. Replace `new Hono()` with `express()`.
2. Replace `c.json()` response helpers with `res.json()`.
3. Replace Hono middleware syntax with Express middleware.
4. Auth middleware pattern stays the same conceptually.

---

### Vector DB: Qdrant → Pinecone

**Scope:** 1-file — replace the retriever module.

```python
# Before (Qdrant)
from qdrant_client import QdrantClient
client = QdrantClient(url=QDRANT_URL)
results = client.search(collection_name="docs", query_vector=embedding, limit=5)

# After (Pinecone)
from pinecone import Pinecone
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index("docs")
results = index.query(vector=embedding, top_k=5, include_metadata=True)
```

**Env change:** Replace `QDRANT_URL` with `PINECONE_API_KEY` + `PINECONE_INDEX`.
**Docker change:** Remove the `qdrant` service from docker-compose.

---

### Vector DB: Qdrant → pgvector

**Scope:** 1-file — use Postgres extension instead of a separate vector DB.

1. Enable the extension: `CREATE EXTENSION IF NOT EXISTS vector;`
2. Add a vector column: `embedding vector(1536)` to your documents table.
3. Query with: `SELECT * FROM documents ORDER BY embedding <=> $1 LIMIT 5;`

**Benefit:** One fewer container. **Trade-off:** Postgres handles both relational and vector queries — fine for <1M vectors, consider dedicated vector DB beyond that.

---

### Relational DB: Postgres → SQLite

**Scope:** Config — change the connection string.

```python
# Before
DATABASE_URL = "postgresql+asyncpg://user:pass@localhost:5432/agent"

# After
DATABASE_URL = "sqlite+aiosqlite:///./agent.db"
```

**Use only for:** Local prototyping. SQLite lacks concurrent writes, proper migrations tooling, and the `vector` extension. Not suitable for production.

---

### Cache: Redis → In-memory

**Scope:** 1-file — replace the rate limiter backend.

```python
# Before (Redis-backed slowapi)
from agent_common.ratelimit import build_limiter
limiter = build_limiter(redis_url="redis://localhost:6379", default_limit="60/minute")

# After (in-memory)
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
```

**Trade-off:** Rate limits are per-process, not shared across instances. Fine for single-instance dev, not for production with multiple replicas.

---

### Tracing: Langfuse → LangSmith

**Scope:** 1-file — replace the observability setup.

1. Replace `langfuse` import with `langsmith`.
2. Swap the callback/decorator pattern (framework-dependent).
3. Update env vars: `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` → `LANGCHAIN_API_KEY`.

See the respective framework docs for callback integration patterns.

---

### Tracing: Skip entirely

**Scope:** Delete — remove tracing calls and the Langfuse container.

1. Remove the `langfuse` service from docker-compose.
2. Remove `LANGFUSE_*` env vars.
3. Remove the observability setup module and any `@observe` decorators or callback handlers.

You lose visibility into LLM calls and costs. Acceptable for prototyping, not recommended for production.

---

### Eval: DeepEval + RAGAS → Promptfoo only

**Scope:** Config — simpler eval pipeline.

Keep `promptfoo.yaml` and the eval dataset. Remove DeepEval and RAGAS Python dependencies.

**Trade-off:** Promptfoo handles assertion-based eval well. You lose DeepEval's metric library (faithfulness, hallucination scores) and RAGAS's RAG-specific metrics. For non-RAG agents, Promptfoo alone is often sufficient.

---

## How to apply swaps

1. **Check the recipe's dependency table** — each blueprint's Environment & Deployment section marks which components are required vs optional.
2. **Load the relevant stack doc** — even for alternatives, the default stack doc explains the integration pattern.
3. **Swap at the module boundary** — all blueprints isolate infrastructure behind thin modules (retriever, rate limiter, observability). Swap the module, not the callers.
4. **Update docker-compose** — add/remove service containers as needed. See [`docs/reference/docker-compose-template.md`](../reference/docker-compose-template.md).
5. **Update .env.example** — add/remove env vars for the new component.
