---
status: Blueprint (validated)
languages: [python, typescript]
agent_pattern: rag
agent_role: "You are a documentation assistant. Answer using only the retrieved documents and cite each source; if the docs do not cover it, say so plainly."
primitives: []
runtime_modes:
  default:
    description: "Anthropic Claude + in-memory keyword retriever + Postgres + Redis + Langfuse. Boots with only ANTHROPIC_API_KEY; Qdrant ships in compose as the production retrieval swap (point QDRANT_URL at it and replace retriever.py)."
    swaps: {}
    context_budget: {input_max: 80000, output_max: 8000}
  local_only:
    description: "Self-hosted vLLM instead of Anthropic Claude — same in-memory keyword retriever, no SaaS keys."
    swaps:
      stack/llm-claude: stack/llm-local-vllm
    context_budget: {input_max: 32000, output_max: 4000}
smoke_test:
  ready: "curl -sf http://localhost:8000/health"
  exercise: |
    curl -sf -X POST http://localhost:8000/ask \
      -H 'content-type: application/json' \
      -d '{"question":"What is the canonical stack?"}'
  assert_jq: '.answer | length > 0'
cost_profile:
  tier: low
  sources: [anthropic]
  typical_run_usd: 0.005
model_recommendation: claude-sonnet-4-6
env_overrides:
  APP_PORT: 8000
  TOP_K: 5
est_tokens: 4200
required_files:
  - Dockerfile
  - docker-compose.yml
  - .github/workflows/ci.yml
  - app/main.py
  - app/agent/qa.py
  - app/tools/chunker.py
  - app/tools/retriever.py
  - tests/unit/test_chunker.py
  - tests/integration/test_query.py
  - tests/eval/test_rag_grounding.py
recipe_dependencies:
  python:
    fastapi: ">=0.110.0"
    pydantic-ai: ">=0.0.13"
    pydantic-settings: ">=2.0.0"
    sqlalchemy: ">=2.0.0"
    asyncpg: ">=0.29.0"
    qdrant-client: ">=1.12.0"
    redis: ">=5.0.0"
    structlog: ">=24.1.0"
    langfuse: ">=2.0.0"
  typescript:
    hono: "^4.0.0"
    "@ai-sdk/anthropic": "^1.0.0"
    ai: "^4.0.0"
    zod: "^3.23.0"
    ioredis: "^5.4.0"
    langfuse: "^3.0.0"
external_services:
  - postgres
  - redis
  - qdrant
  - langfuse
capabilities:
  - relational.postgres
  - cache.redis
  - vector_db.qdrant
  - obs.langfuse
  - eval.promptfoo
bootstrap_config:
  vector_collections:
    - { name: docs_rag, vector_size: 1536, distance: cosine }
acceptance_contracts:
  http_endpoints:
    - {path: /health, method: GET, status: 200}
    - {path: /ask, method: POST, status: 200}
  required_env:
    - {name: ANTHROPIC_API_KEY, source: prompted}
    - {name: DATABASE_URL, source: 'capability:relational.postgres'}
  required_compose_services: [postgres, redis, qdrant, langfuse]
  smoke_assertions:
    - {jq: '.answer | length > 0', against: smoke_test.exercise.stdout}
topology: single
load_list:
  - {path: https://github.com/jagguvarma15/agent-blueprints/blob/main/patterns/rag/overview.md, required: true}
  - {path: ../frameworks/pydantic-ai.md, required: true, when: "language == 'python'"}
  - {path: ../frameworks/vercel-ai-sdk.md, required: true, when: "language == 'typescript'"}
  - {path: ../cross-cutting/project-layout.md, required: true}
  - {path: ../stack/llm-claude.md, required: true}
  - {path: ../stack/vector-qdrant.md, required: true, when: "capabilities contains 'vector_db.qdrant'"}
  - {path: ../stack/api-fastapi.md, required: false, when: "language == 'python'"}
  - {path: ../stack/api-hono.md, required: false, when: "language == 'typescript'"}
  - {path: ../stack/relational-postgres.md, required: false, when: "capabilities contains 'relational.postgres'"}
  - {path: ../stack/cache-redis.md, required: false, when: "capabilities contains 'cache.redis'"}
  - {path: ../stack/tracing-langfuse.md, required: false, when: "capabilities contains 'obs.langfuse'"}
  - {path: ../cross-cutting/auth-jwt.md, required: false}
  - {path: ../cross-cutting/logging-structured.md, required: false}
  - {path: ../cross-cutting/observability.md, required: false}
  - {path: ../cross-cutting/rate-limiting.md, required: false}
  - {path: ../cross-cutting/prompt-management.md, required: false}
---

# Recipe: docs-rag-qa

**Status:** Blueprint (validated)

## Composes

- Pattern: [RAG](https://github.com/jagguvarma15/agent-blueprints/blob/main/patterns/rag/overview.md)
- Framework (Py): [Pydantic AI](../frameworks/pydantic-ai.md) (agentic RAG with tool-based retrieval)
- Framework (TS): [Vercel AI SDK](../frameworks/vercel-ai-sdk.md) (tool-based retrieval via `generateText`)
- Stack: [FastAPI](../stack/api-fastapi.md) / [Hono](../stack/api-hono.md), [Postgres](../stack/relational-postgres.md), [Redis](../stack/cache-redis.md), [Qdrant](../stack/vector-qdrant.md), [Langfuse](../stack/tracing-langfuse.md)
- Cross-cutting: [Auth](../cross-cutting/auth-jwt.md), [Logging](../cross-cutting/logging-structured.md), [Observability](../cross-cutting/observability.md), [Rate limiting](../cross-cutting/rate-limiting.md)

### Load list

Feed these files to your AI coding assistant to build this agent:

**Core (always load):**
- `docs/recipes/docs-rag-qa.md` — this blueprint
- `https://github.com/jagguvarma15/agent-blueprints/blob/main/patterns/rag/overview.md` — the RAG pattern
- `docs/frameworks/pydantic-ai.md` (Python) or `docs/frameworks/vercel-ai-sdk.md` (TypeScript)
- `docs/stack/llm-claude.md` — LLM integration and model selection

**Stack (load for Tier 2 — API-ready):**
- `docs/stack/api-fastapi.md` or `docs/stack/api-hono.md` — API layer
- `docs/stack/relational-postgres.md` — document metadata storage
- `docs/stack/cache-redis.md` — rate limiting backend
- `docs/stack/vector-qdrant.md` — vector retrieval (core to this pattern)

**Production concerns (load for Tier 3):**
- `docs/cross-cutting/auth-jwt.md` · `docs/cross-cutting/rate-limiting.md` · `docs/cross-cutting/logging-structured.md` · `docs/cross-cutting/observability.md` · `docs/cross-cutting/testing-strategy.md`

**Scaffolding:** `docs/reference/docker-templates.md` · `docs/reference/docker-compose-template.md`

### Generation prompt

Copy-paste this into Claude Code or Cursor to scaffold this recipe before `agent-scaffold` ships:

````
You are scaffolding a runnable agent project from a spec at https://github.com/jagguvarma15/agent-deployments.

Step 1 — Fetch:
  - https://raw.githubusercontent.com/jagguvarma15/agent-deployments/main/catalog.yaml
  - https://raw.githubusercontent.com/jagguvarma15/agent-deployments/main/docs/recipes/docs-rag-qa.md
  - Every `load_list[].path` with `required: true` and `cache_tier: hot`.

Step 2 — Generate the project at `./docs-rag-qa/` matching the recipe's `required_files[]`:
  - model(s): claude-sonnet-4-6
  - framework: pydantic-ai (Python) or vercel-ai-sdk (TS)
  - runtime_mode: default
  - env vars: from `catalog.recipes[docs-rag-qa].env_contract`

Step 3 — Bring it up: `docker compose up` + bootstrap per `LAYER_ORDER`.

Step 4 — Run the smoke test:

     curl -sf -X POST http://localhost:8000/ask \
       -H 'content-type: application/json' \
       -d '{"question":"What is the canonical stack?"}'

Step 5 — Validate against `catalog.recipes[docs-rag-qa].acceptance_contracts`.
````

## What it does

A document Q&A agent. Users ingest documents (which get chunked and stored), then ask natural-language questions. The agent retrieves relevant chunks via a tool call, synthesizes an answer grounded in the retrieved context, and returns the answer with citations.

This implements **agentic RAG** -- the LLM decides when and what to retrieve, rather than retrieval being a fixed pipeline step. The agent has a `search_knowledge_base` tool and autonomously decides how to query it.

## Architecture

```
                    ┌─────────────┐
                    │   Client    │
                    └──────┬──────┘
                           │
              POST /documents   POST /query
                           │
                    ┌──────▼──────┐
                    │   FastAPI   │ (or Hono)
                    │   + Auth    │
                    │   + Rate    │
                    └──┬──────┬──┘
                       │      │
            ┌──────────▼┐  ┌──▼──────────┐
            │  Ingest   │  │  QA Agent   │
            │  Pipeline │  │ (Pydantic AI│
            │           │  │  / AI SDK)  │
            └──┬────┬───┘  └──┬──────────┘
               │    │         │
    ┌──────────▼┐ ┌─▼───┐  ┌─▼──────────┐
    │ Chunker   │ │ DB  │  │ Retriever  │
    │ (sentence │ │(PG) │  │ (Qdrant /  │
    │  split +  │ │     │  │  in-memory)│
    │  overlap) │ │     │  │            │
    └───────────┘ └─────┘  └────────────┘
```

### Ingest flow

1. Client POSTs a document (title + content) to `/documents`.
2. Chunker splits content into overlapping sentence-boundary chunks (default: 500 chars, 50 char overlap).
3. Document metadata saved to Postgres (`documents` table).
4. Chunks saved to Postgres (`chunks` table) and to the vector store for retrieval.

### Query flow

1. Client POSTs a question to `/query`.
2. QA agent receives the question with a system prompt instructing it to use retrieval.
3. Agent calls `search_knowledge_base` tool with a query string.
4. Retriever returns top-K matching chunks with scores.
5. Agent synthesizes an answer grounded in the retrieved chunks.
6. Response includes the answer, citations, and a trace ID.

## Data Models

### Python (Pydantic)

```python
from pydantic import BaseModel, Field


class DocumentIngestRequest(BaseModel):
    content: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    metadata: dict | None = None


class DocumentIngestResponse(BaseModel):
    document_id: str
    chunk_count: int
    status: str


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class Citation(BaseModel):
    chunk_id: str
    document_title: str
    text: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    trace_id: str
```

### TypeScript (Zod)

```typescript
import { z } from "zod";

export const DocumentIngestRequest = z.object({
  content: z.string().min(1),
  title: z.string().min(1),
  metadata: z.record(z.unknown()).optional(),
});
export const QueryRequest = z.object({
  question: z.string().min(1),
  top_k: z.number().min(1).max(20).default(5),
});
export const Citation = z.object({
  chunk_id: z.string(),
  document_title: z.string(),
  text: z.string(),
  score: z.number(),
});
export const QueryResponse = z.object({
  answer: z.string(),
  citations: z.array(Citation),
  trace_id: z.string(),
});
```

## API Contract

### `POST /documents`

Ingest a document into the knowledge base.

**Request:**

```json
{
  "title": "MCP Overview",
  "content": "The Model Context Protocol (MCP) is an open standard..."
}
```

**Response (200):**

```json
{
  "document_id": "a1b2c3d4-...",
  "chunk_count": 3,
  "status": "ingested"
}
```

### `POST /query`

Ask a question against the knowledge base.

**Request:**

```json
{
  "question": "What is MCP?",
  "top_k": 5
}
```

**Response (200):**

```json
{
  "answer": "MCP (Model Context Protocol) is an open standard for connecting AI models to external data sources and tools...",
  "citations": [
    {"chunk_id": "ch-1", "document_title": "MCP Overview", "text": "The Model Context Protocol...", "score": 0.92}
  ],
  "trace_id": "e5f6g7h8-..."
}
```

**Errors:**

| Status | Body | When |
|--------|------|------|
| 400 | `{"error": "Invalid request", "details": [...]}` | Missing question or content |
| 500 | `{"error": "Internal error"}` | LLM or retrieval failure |

### `GET /health`

Returns `{"status": "ok"}`.

## Tool Specifications

### `search_knowledge_base`

| Field | Value |
|-------|-------|
| **Description** | Search the document knowledge base for chunks relevant to a query. Uses keyword matching (dev) or vector similarity (production with Qdrant). |
| **Parameter** | `query` (string, required) — Natural language search query. |
| **Return type** | `string` — Formatted matching chunks with document titles and scores, separated by dividers. Returns `"No relevant documents found."` if no matches. |

## Prompt Specifications

### QA System Prompt

```
You are a document Q&A assistant. Your job is to answer questions
based on the documents in the knowledge base.

When answering:
1. Use the search_knowledge_base tool to find relevant document chunks.
2. Base your answer ONLY on the retrieved content.
3. Include citations referencing the source documents.
4. If no relevant information is found, say so clearly.

Always provide accurate, concise answers with proper citations.
```

**Design rationale:**
- **"Use the search_knowledge_base tool"** — Explicitly instructs the agent to call retrieval rather than relying on parametric memory. Core of agentic RAG.
- **"Base your answer ONLY on the retrieved content"** — Prevents hallucination by grounding strictly in retrieved chunks.
- **"Include citations"** — Makes answers auditable. Users can trace claims to specific documents.
- **"If no relevant information is found, say so clearly"** — Prevents fabrication when the KB lacks coverage.

## Key files

> Follows the canonical [project layout](../cross-cutting/project-layout.md) — `app/` package for Python, `src/` for TypeScript, `tests/{unit,integration,eval}/` for both.

### Python track

| File | Role |
|------|------|
| `app/main.py` | FastAPI app with lifespan (DB init, logging config) |
| `app/settings.py` | Pydantic-settings config (model, DB, Qdrant, Langfuse) |
| `app/agent/qa.py` | Pydantic AI agent with `search_knowledge_base` tool |
| `app/api/query.py` | `/query` endpoint -- runs agent, returns answer + citations |
| `app/api/documents.py` | `/documents` endpoint -- ingest, chunk, store |
| `app/tools/chunker.py` | Sentence-boundary chunking with configurable size/overlap |
| `app/tools/retriever.py` | In-memory keyword search (swap point for Qdrant) |
| `app/db/models.py` | SQLAlchemy models: `Document`, `Chunk` |
| `app/models/schemas.py` | Pydantic request/response schemas |
| `docker-compose.yml` | Extends base: Postgres + Redis + Langfuse + app |
| `eval/dataset.jsonl` | Golden Q&A pairs for eval |
| `eval/promptfoo.yaml` | Promptfoo red-team config |

### TypeScript track

| File | Role |
|------|------|
| `src/index.ts` | Hono app entry point |
| `src/config.ts` | Zod-validated config from env |
| `src/agent/qa.ts` | Vercel AI SDK agent with `search_knowledge_base` tool |
| `src/api/query.ts` | `/query` route handler |
| `src/api/documents.ts` | `/documents` route handler |
| `src/tools/chunker.ts` | Sentence-boundary chunking |
| `src/tools/retriever.ts` | In-memory keyword search (swap point for Qdrant) |
| `src/schemas/index.ts` | Zod request/response schemas |

## Implementation Roadmap

| Step | Task | Key deliverables |
|------|------|-----------------|
| 1 | **Project scaffolding** | FastAPI/Hono app with `/health`, settings, structured logging |
| 2 | **Data models** | Pydantic + Zod schemas for ingest, query, citation, response |
| 3 | **Database models** | Document and Chunk tables with SQLAlchemy |
| 4 | **Chunker** | Sentence-boundary splitting with configurable size (500) and overlap (50) |
| 5 | **Retriever** | In-memory keyword search (swap point for Qdrant) |
| 6 | **QA agent** | Pydantic AI agent with `search_knowledge_base` tool |
| 7 | **Ingest endpoint** | `POST /documents` — chunk, store in DB and retriever |
| 8 | **Query endpoint** | `POST /query` — run agent, return answer + citations |
| 9 | **Cross-cutting** | JWT auth, rate limiting, Langfuse tracing |
| 10 | **Unit tests** | Chunker logic, schema validation, API routes with mocked agent |
| 11 | **Integration + eval** | End-to-end pipeline with real LLM, promptfoo security scan |

## Environment & Deployment

### Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `QA_MODEL` | No | `claude-sonnet-4-6-20250514` | Model for the QA agent |
| `CHUNK_SIZE` | No | `500` | Max chunk size in characters |
| `CHUNK_OVERLAP` | No | `50` | Overlap between chunks |
| `DATABASE_URL` | No | `postgresql+asyncpg://agent:agent@localhost:5432/agent_db` | Postgres connection |
| `REDIS_URL` | No | `redis://localhost:6379` | Redis for rate limiting |
| `QDRANT_URL` | No | `http://localhost:6333` | Qdrant vector DB URL |
| `QDRANT_COLLECTION` | No | `docs_rag` | Qdrant collection name |
| `LANGFUSE_PUBLIC_KEY` | No | `pk-lf-local` | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | No | `sk-lf-local` | Langfuse secret key |
| `LANGFUSE_HOST` | No | `http://localhost:3000` | Langfuse server URL |
| `JWT_SECRET` | No | `change-me-in-production` | JWT signing secret |
| `APP_ENV` | No | `development` | Environment name |
| `LOG_LEVEL` | No | `INFO` | Log level |

### Docker Compose

See [Docker Compose template](../reference/docker-compose-template.md) for base infrastructure. This agent needs: Postgres, Redis, Qdrant, Langfuse.

### Infrastructure dependencies

| Component | Required? | Why |
|-----------|-----------|-----|
| Postgres | Yes | Document metadata and ingest tracking |
| Redis | Yes | Rate limiting backend |
| Qdrant | Yes | Vector retrieval — core to RAG (can start with in-memory keyword search for prototyping) |
| Langfuse | Recommended | LLM + retrieval tracing (skip for local dev) |

## Test Strategy

### Unit tests

```python
def test_chunker_empty_input():
    """Empty string returns empty list."""
    assert chunk_document("") == []

def test_chunker_respects_overlap():
    """Consecutive chunks overlap by the configured amount."""
    chunks = chunk_document("A. B. C. D. E. F.", chunk_size=10, overlap=5)
    # Verify overlap between adjacent chunks

def test_query_returns_citations(mock_llm_client):
    """Query endpoint returns answer with trace_id."""
    response = await client.post("/query", json={"question": "What is MCP?"})
    assert response.status_code == 200
    assert "trace_id" in response.json()
```

### Eval assertions

- Answers are grounded in retrieved chunks (faithfulness)
- Agent always calls `search_knowledge_base` before answering
- "I don't know" for questions outside KB coverage (no hallucination)
- Chunker produces correct boundary splits

## Eval Dataset

Inline golden cases for the RAG pipeline. Each case names the seed documents the test harness ingests before posting `question` to `/query`; assertions check the response against `expected_documents` (retrieved chunks include these doc titles) and `expected_answer_contains` (the answer body contains each string, case-insensitive).

### Case 1 — High-confidence single-document match

```json
{
  "id": "rag-001",
  "category": "happy-path",
  "seed_documents": [
    {"title": "MCP Overview", "content": "The Model Context Protocol (MCP) is an open standard for connecting AI models to external data sources and tools. It provides a unified interface that works across different AI frameworks and model providers."}
  ],
  "question": "What is MCP?",
  "expected_documents": ["MCP Overview"],
  "expected_answer_contains": ["Model Context Protocol", "open standard"]
}
```

### Case 2 — Out-of-corpus question, graceful refusal

```json
{
  "id": "rag-002",
  "category": "refusal",
  "seed_documents": [
    {"title": "MCP Overview", "content": "The Model Context Protocol (MCP) is an open standard for connecting AI models to external data sources."}
  ],
  "question": "What is the capital of France?",
  "expected_documents": [],
  "expected_answer_contains": ["don't know", "not in", "no relevant"]
}
```

### Case 3 — Ambiguous question requiring hybrid filter

```json
{
  "id": "rag-003",
  "category": "ambiguous",
  "seed_documents": [
    {"title": "Python Threading", "content": "Python's GIL serializes bytecode execution across threads, limiting CPU-bound parallelism."},
    {"title": "Java Threading", "content": "Java threads run on top of OS threads with no GIL. CPU-bound workloads can parallelize across cores."}
  ],
  "question": "How do threads work?",
  "expected_documents": ["Python Threading", "Java Threading"],
  "expected_answer_contains": ["GIL", "OS threads"]
}
```

### Case 4 — Multi-doc synthesis

```json
{
  "id": "rag-004",
  "category": "synthesis",
  "seed_documents": [
    {"title": "Postgres Indexes", "content": "B-tree indexes are the default in Postgres. They support equality and range queries on ordered data."},
    {"title": "Qdrant Index", "content": "Qdrant uses HNSW (Hierarchical Navigable Small World) graphs for approximate nearest-neighbor vector search."}
  ],
  "question": "Compare how Postgres and Qdrant index their data.",
  "expected_documents": ["Postgres Indexes", "Qdrant Index"],
  "expected_answer_contains": ["B-tree", "HNSW", "nearest-neighbor"]
}
```

### Case 5 — Query that should produce zero matches in a populated KB

```json
{
  "id": "rag-005",
  "category": "no-match",
  "seed_documents": [
    {"title": "MCP Overview", "content": "The Model Context Protocol is an open standard."}
  ],
  "question": "Explain how WebRTC handles NAT traversal.",
  "expected_documents": [],
  "expected_answer_contains": ["don't know", "not in", "no relevant"]
}
```

See [eval-data guide](../cross-cutting/eval-data.md) for generation + curation patterns.

## Design Decisions

- **Agentic RAG over naive RAG:** The LLM decides when to retrieve, enabling multi-turn refinement. Trade-off: slightly higher latency from the tool-call round trip.
- **In-memory retriever as default:** Keeps `make up` instant with no embedding model dependency, so the `default` runtime mode boots with only `ANTHROPIC_API_KEY`. Production retrieval is the documented swap, not a separate runtime mode (the swap grammar replaces capabilities rather than adding them, and no local embedding/rerank capability exists to pair against): point `QDRANT_URL` at the Qdrant instance that already ships in `docker-compose.yml`, replace `retriever.py` with Qdrant client calls, and — for higher recall — embed with OpenAI (`OPENAI_API_KEY`) and re-rank with Cohere (`COHERE_API_KEY`). Those two SaaS sources are billed only when you opt into hosted retrieval, which is why `cost_profile.sources` lists only `anthropic` for the default.
- **Pydantic AI over LangGraph (Python):** For a single-agent RAG pipeline, Pydantic AI's tool decorator is simpler than a LangGraph state graph. LangGraph becomes the better choice if you add multi-step retrieval, re-ranking, or human-in-the-loop.
- **Vercel AI SDK over Mastra (TypeScript):** The `generateText` + `tool()` pattern is clean and minimal for this use case. Mastra would add value if you needed built-in RAG primitives or workflow orchestration.

## Reference Implementation

### Python

<details>
<summary><code>app/main.py</code></summary>

```python
"""FastAPI entrypoint for docs-rag-qa."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api.documents import router as documents_router
from app.api.query import router as query_router
from app.db.models import Base
from app.db.session import engine
from app.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    from agent_common.logs import configure

    configure(settings.app_name, env=settings.app_env, log_level=settings.log_level)

    logger = structlog.get_logger()
    logger.info("starting", app=settings.app_name)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)

app.include_router(documents_router)
app.include_router(query_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

</details>

<details>
<summary><code>app/settings.py</code></summary>

```python
"""Application settings via pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "docs-rag-qa"
    app_env: str = "development"
    log_level: str = "INFO"
    anthropic_api_key: str = ""
    qa_model: str = "claude-sonnet-4-6-20250514"
    chunk_size: int = 500
    chunk_overlap: int = 50
    database_url: str = "postgresql+asyncpg://agent:agent@localhost:5432/agent_db"
    redis_url: str = "redis://localhost:6379"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "docs_rag"
    jwt_secret: str = "change-me-in-production"
    langfuse_public_key: str = "pk-lf-local"
    langfuse_secret_key: str = "sk-lf-local"
    langfuse_host: str = "http://localhost:3000"
    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
```

</details>

<details>
<summary><code>app/models/schemas.py</code></summary>

```python
"""Pydantic models for request/response validation."""

from pydantic import BaseModel


class DocumentIngestRequest(BaseModel):
    content: str
    title: str
    metadata: dict | None = None


class DocumentIngestResponse(BaseModel):
    document_id: str
    chunk_count: int
    status: str


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5


class Citation(BaseModel):
    chunk_id: str
    document_title: str
    text: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    trace_id: str
```

</details>

<details>
<summary><code>app/agent/qa.py</code></summary>

```python
"""Q&A agent using Pydantic AI with retrieval tool."""

from pydantic_ai import Agent

from app.settings import settings
from app.tools.retriever import search_similar

QA_SYSTEM_PROMPT = """You are a document Q&A assistant. Your job is to answer questions
based on the documents in the knowledge base.

When answering:
1. Use the search_knowledge_base tool to find relevant document chunks.
2. Base your answer ONLY on the retrieved content.
3. Include citations referencing the source documents.
4. If no relevant information is found, say so clearly.

Always provide accurate, concise answers with proper citations."""

_qa_agent: Agent | None = None


def _get_agent() -> Agent:
    global _qa_agent
    if _qa_agent is None:
        _qa_agent = Agent(
            f"anthropic:{settings.qa_model}",
            system_prompt=QA_SYSTEM_PROMPT,
        )

        @_qa_agent.tool_plain
        def search_knowledge_base(query: str, top_k: int = 5) -> str:
            """Search the knowledge base for relevant document chunks."""
            return search_similar(query, top_k=top_k)

    return _qa_agent


async def answer_question(question: str, top_k: int = 5) -> tuple[str, list[dict]]:
    """Answer a question using the Q&A agent."""
    agent = _get_agent()
    result = await agent.run(f"Answer this question (retrieve up to {top_k} chunks): {question}")

    citations: list[dict] = []
    for msg in result.all_messages():
        if hasattr(msg, "parts"):
            for part in msg.parts:
                if hasattr(part, "tool_name") and part.tool_name == "search_knowledge_base":
                    citations.append({
                        "tool": part.tool_name,
                        "args": part.args if hasattr(part, "args") else {},
                    })

    return result.data, citations
```

</details>

<details>
<summary><code>app/api/documents.py</code></summary>

```python
"""Document ingestion route handlers."""

import hashlib
import uuid

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Document
from app.db.session import get_session
from app.models.schemas import DocumentIngestRequest, DocumentIngestResponse
from app.tools.chunker import chunk_document
from app.tools.retriever import store_chunks

logger = structlog.get_logger()

router = APIRouter()


@router.post("/documents", response_model=DocumentIngestResponse)
async def ingest_document(
    request: DocumentIngestRequest,
    session: AsyncSession = Depends(get_session),
):
    """Ingest a document: chunk it, store in DB and vector store."""
    doc_id = str(uuid.uuid4())
    content_hash = hashlib.sha256(request.content.encode()).hexdigest()

    log = logger.bind(document_id=doc_id, title=request.title)
    log.info("ingesting_document")

    chunks = chunk_document(request.content)
    log.info("document_chunked", chunk_count=len(chunks))

    document = Document(
        id=doc_id,
        title=request.title,
        content_hash=content_hash,
        chunk_count=len(chunks),
    )
    session.add(document)

    for i, chunk_text in enumerate(chunks):
        chunk = Chunk(
            document_id=doc_id,
            text=chunk_text,
            position=i,
        )
        session.add(chunk)

    await session.commit()

    store_chunks(doc_id, request.title, chunks)

    return DocumentIngestResponse(
        document_id=doc_id,
        chunk_count=len(chunks),
        status="ingested",
    )
```

</details>

<details>
<summary><code>app/api/query.py</code></summary>

```python
"""Query route handlers."""

import uuid

import structlog
from fastapi import APIRouter

from app.agent.qa import answer_question
from app.models.schemas import QueryRequest, QueryResponse

logger = structlog.get_logger()

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Answer a question using the RAG pipeline."""
    trace_id = str(uuid.uuid4())
    log = logger.bind(trace_id=trace_id, question=request.question)
    log.info("processing_query")

    answer, citations = await answer_question(request.question, top_k=request.top_k)
    log.info("query_answered", citation_count=len(citations))

    return QueryResponse(
        answer=answer,
        citations=[],
        trace_id=trace_id,
    )
```

</details>

<details>
<summary><code>app/tools/chunker.py</code></summary>

```python
"""Document chunking utilities."""

import re


def chunk_document(content: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks by sentence boundaries."""
    if not content or not content.strip():
        return []

    sentences = re.split(r"(?<=[.!?])\s+", content.strip())
    sentences = [s for s in sentences if s.strip()]

    if not sentences:
        return []

    chunks: list[str] = []
    current_chunk = ""

    for sentence in sentences:
        candidate = f"{current_chunk} {sentence}".strip() if current_chunk else sentence

        if len(candidate) > chunk_size and current_chunk:
            chunks.append(current_chunk)
            if overlap > 0 and len(current_chunk) > overlap:
                current_chunk = current_chunk[-overlap:] + " " + sentence
            else:
                current_chunk = sentence
        else:
            current_chunk = candidate

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks
```

</details>

<details>
<summary><code>app/tools/retriever.py</code></summary>

```python
"""In-memory mock vector store for document retrieval."""

import uuid

_document_store: dict[str, list[dict]] = {}


def store_chunks(document_id: str, title: str, chunks: list[str]) -> None:
    """Store document chunks in the in-memory store."""
    entries = []
    for i, chunk_text in enumerate(chunks):
        entries.append({
            "chunk_id": str(uuid.uuid4()),
            "document_id": document_id,
            "document_title": title,
            "text": chunk_text,
            "position": i,
        })
    _document_store[document_id] = entries


def search_similar(query: str, top_k: int = 5) -> str:
    """Search for chunks similar to the query using keyword matching."""
    query_words = set(query.lower().split())
    scored: list[tuple[float, dict]] = []

    for doc_chunks in _document_store.values():
        for chunk in doc_chunks:
            chunk_words = set(chunk["text"].lower().split())
            overlap = len(query_words & chunk_words)
            if overlap > 0:
                score = overlap / max(len(query_words), 1)
                scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_results = scored[:top_k]

    if not top_results:
        return "No relevant documents found."

    parts: list[str] = []
    for score, chunk in top_results:
        parts.append(
            f"[{chunk['document_title']}] (score: {score:.2f})\n{chunk['text']}"
        )
    return "\n\n---\n\n".join(parts)
```

</details>

<details>
<summary><code>app/db/models.py</code></summary>

```python
"""SQLAlchemy models for documents and chunks."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    content_hash = Column(String, nullable=False)
    chunk_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    chunks = relationship("Chunk", back_populates="document", order_by="Chunk.position")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    position = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    document = relationship("Document", back_populates="chunks")
```

</details>

### TypeScript

<details>
<summary><code>src/index.ts</code></summary>

```typescript
import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { documentsRouter } from "./api/documents.js";
import { queryRouter } from "./api/query.js";

const app = new Hono();

app.get("/health", (c) => c.json({ status: "ok" }));
app.route("/", documentsRouter);
app.route("/", queryRouter);

const port = Number(process.env.PORT ?? 8000);

serve({ fetch: app.fetch, port }, (info) => {
  console.log(`docs-rag-qa running at http://localhost:${info.port}`);
});

export default app;
```

</details>

<details>
<summary><code>src/config.ts</code></summary>

```typescript
import { z } from "zod";

const configSchema = z.object({
  appName: z.string().default("docs-rag-qa"),
  appEnv: z.string().default("development"),
  logLevel: z.string().default("info"),
  anthropicApiKey: z.string().default(""),
  qaModel: z.string().default("claude-sonnet-4-6-20250514"),
  chunkSize: z.coerce.number().default(500),
  chunkOverlap: z.coerce.number().default(50),
  databaseUrl: z.string().default("postgresql://agent:agent@localhost:5432/agent_db"),
  redisUrl: z.string().default("redis://localhost:6379"),
  qdrantUrl: z.string().default("http://localhost:6333"),
  qdrantCollection: z.string().default("docs_rag"),
  jwtSecret: z.string().default("change-me-in-production"),
  langfusePublicKey: z.string().default("pk-lf-local"),
  langfuseSecretKey: z.string().default("sk-lf-local"),
  langfuseHost: z.string().default("http://localhost:3000"),
});

export const config = configSchema.parse({
  appName: process.env.APP_NAME,
  appEnv: process.env.APP_ENV,
  logLevel: process.env.LOG_LEVEL,
  anthropicApiKey: process.env.ANTHROPIC_API_KEY,
  qaModel: process.env.QA_MODEL,
  chunkSize: process.env.CHUNK_SIZE,
  chunkOverlap: process.env.CHUNK_OVERLAP,
  databaseUrl: process.env.DATABASE_URL,
  redisUrl: process.env.REDIS_URL,
  qdrantUrl: process.env.QDRANT_URL,
  qdrantCollection: process.env.QDRANT_COLLECTION,
  jwtSecret: process.env.JWT_SECRET,
  langfusePublicKey: process.env.LANGFUSE_PUBLIC_KEY,
  langfuseSecretKey: process.env.LANGFUSE_SECRET_KEY,
  langfuseHost: process.env.LANGFUSE_HOST,
});

export type Config = z.infer<typeof configSchema>;
```

</details>

<details>
<summary><code>src/schemas/index.ts</code></summary>

```typescript
import { z } from "zod";

export const DocumentIngestRequest = z.object({
  content: z.string().min(1),
  title: z.string().min(1),
  metadata: z.record(z.unknown()).optional(),
});
export type DocumentIngestRequest = z.infer<typeof DocumentIngestRequest>;

export const DocumentIngestResponse = z.object({
  document_id: z.string(),
  chunk_count: z.number(),
  status: z.string(),
});
export type DocumentIngestResponse = z.infer<typeof DocumentIngestResponse>;

export const QueryRequest = z.object({
  question: z.string().min(1),
  top_k: z.number().default(5),
});
export type QueryRequest = z.infer<typeof QueryRequest>;

export const Citation = z.object({
  chunk_id: z.string(),
  document_title: z.string(),
  text: z.string(),
  score: z.number(),
});
export type Citation = z.infer<typeof Citation>;

export const QueryResponse = z.object({
  answer: z.string(),
  citations: z.array(Citation),
  trace_id: z.string(),
});
export type QueryResponse = z.infer<typeof QueryResponse>;
```

</details>

<details>
<summary><code>src/agent/qa.ts</code></summary>

```typescript
/**
 * QA agent using Vercel AI SDK with retrieval tool.
 */

import { anthropic } from "@ai-sdk/anthropic";
import { generateText, tool } from "ai";
import { z } from "zod";
import { config } from "../config.js";
import { searchSimilar } from "../tools/retriever.js";

const QA_SYSTEM_PROMPT = `You are a document Q&A assistant.
Given a user question, search the knowledge base for relevant content,
then provide a clear, accurate answer with citations to the source documents.
Always cite which document your answer comes from.`;

export async function answerQuestion(
  question: string,
  topK = 5,
): Promise<{
  text: string;
  toolCalls: Array<{ toolName: string; args: Record<string, unknown> }>;
}> {
  const qaTools = {
    search_knowledge_base: tool({
      description: "Search the document knowledge base for relevant chunks",
      parameters: z.object({ query: z.string() }),
      execute: async ({ query }) => searchSimilar(query, topK),
    }),
  };

  const result = await generateText({
    model: anthropic(config.qaModel),
    system: QA_SYSTEM_PROMPT,
    prompt: question,
    tools: qaTools,
    maxSteps: 3,
  });

  const toolCalls = result.steps
    .flatMap((s) => s.toolCalls)
    .map((tc: { toolName: string; args: unknown }) => ({
      toolName: tc.toolName,
      args: tc.args as Record<string, unknown>,
    }));

  return { text: result.text, toolCalls };
}
```

</details>

<details>
<summary><code>src/api/documents.ts</code></summary>

```typescript
/**
 * Document ingestion route handler.
 */

import { Hono } from "hono";
import { DocumentIngestRequest } from "../schemas/index.js";
import { chunkDocument } from "../tools/chunker.js";
import { storeChunks } from "../tools/retriever.js";

export const documentsRouter = new Hono();

documentsRouter.post("/documents", async (c) => {
  const body = await c.req.json();
  const parsed = DocumentIngestRequest.safeParse(body);

  if (!parsed.success) {
    return c.json(
      { error: "Invalid request", details: parsed.error.issues },
      400,
    );
  }

  const { content, title } = parsed.data;
  const documentId = crypto.randomUUID();
  const chunks = chunkDocument(content);

  storeChunks(documentId, title, chunks);

  return c.json({
    document_id: documentId,
    chunk_count: chunks.length,
    status: "ingested",
  });
});
```

</details>

<details>
<summary><code>src/api/query.ts</code></summary>

```typescript
/**
 * Query route handler.
 */

import { Hono } from "hono";
import { answerQuestion } from "../agent/qa.js";
import { QueryRequest } from "../schemas/index.js";

export const queryRouter = new Hono();

queryRouter.post("/query", async (c) => {
  const body = await c.req.json();
  const parsed = QueryRequest.safeParse(body);

  if (!parsed.success) {
    return c.json(
      { error: "Invalid request", details: parsed.error.issues },
      400,
    );
  }

  const { question, top_k } = parsed.data;
  const traceId = crypto.randomUUID();

  const { text } = await answerQuestion(question, top_k);

  return c.json({
    answer: text,
    citations: [],
    trace_id: traceId,
  });
});
```

</details>

<details>
<summary><code>src/tools/chunker.ts</code></summary>

```typescript
/**
 * Document chunking utility.
 */

export function chunkDocument(
  content: string,
  chunkSize = 500,
  overlap = 50,
): string[] {
  if (!content.trim()) return [];

  const sentences = content.match(/[^.!?]+[.!?]+\s*/g) ?? [content];
  const chunks: string[] = [];
  let current = "";

  for (const sentence of sentences) {
    if (current.length + sentence.length > chunkSize && current.length > 0) {
      chunks.push(current.trim());
      const words = current.split(/\s+/);
      const overlapWords = words.slice(
        Math.max(0, words.length - Math.ceil(overlap / 5)),
      );
      current = `${overlapWords.join(" ")} ${sentence}`;
    } else {
      current += sentence;
    }
  }

  if (current.trim()) {
    chunks.push(current.trim());
  }

  return chunks;
}
```

</details>

<details>
<summary><code>src/tools/retriever.ts</code></summary>

```typescript
/**
 * In-memory mock vector store with keyword-based retrieval.
 */

interface StoredChunk {
  chunkId: string;
  documentTitle: string;
  text: string;
}

const documentStore: Map<string, StoredChunk[]> = new Map();

export function storeChunks(
  documentId: string,
  title: string,
  chunks: string[],
): void {
  const stored: StoredChunk[] = chunks.map((text, i) => ({
    chunkId: `${documentId}-chunk-${i}`,
    documentTitle: title,
    text,
  }));
  documentStore.set(documentId, stored);
}

export function searchSimilar(query: string, topK = 5): string {
  const words = query.toLowerCase().split(/\s+/);
  const scored: Array<[number, StoredChunk]> = [];

  for (const chunks of documentStore.values()) {
    for (const chunk of chunks) {
      const text = chunk.text.toLowerCase();
      const score = words.filter((w) => text.includes(w)).length;
      if (score > 0) scored.push([score, chunk]);
    }
  }

  scored.sort((a, b) => b[0] - a[0]);
  const top = scored.slice(0, topK);

  if (top.length === 0) {
    return "No relevant documents found.";
  }

  return top
    .map(
      ([score, chunk]) =>
        `[${chunk.documentTitle}] (score: ${score})\n${chunk.text}`,
    )
    .join("\n\n---\n\n");
}

export function clearStore(): void {
  documentStore.clear();
}
```

</details>

### Configuration & Eval

<details>
<summary><code>.env.example</code></summary>

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Postgres
POSTGRES_USER=agent
POSTGRES_PASSWORD=agent
POSTGRES_DB=agent_db
DATABASE_URL=postgresql://agent:agent@localhost:5432/agent_db

# Redis
REDIS_URL=redis://localhost:6379

# Langfuse
LANGFUSE_PUBLIC_KEY=pk-lf-local
LANGFUSE_SECRET_KEY=sk-lf-local
LANGFUSE_HOST=http://localhost:3000

# JWT
JWT_SECRET=change-me-in-production

# App
APP_ENV=development
LOG_LEVEL=INFO
```

</details>

<details>
<summary><code>eval/promptfoo.yaml</code></summary>

```yaml
description: "Security scan for docs-rag-qa"

prompts:
  - "{{message}}"

providers:
  - id: http
    config:
      url: http://localhost:8000/health
      method: GET

redteam:
  plugins:
    - prompt-injection
    - jailbreak
    - pii
```

</details>

## Example interaction

### Ingest a document

```bash
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "MCP Overview",
    "content": "The Model Context Protocol (MCP) is an open standard for connecting AI models to external data sources and tools. It provides a unified interface that works across different AI frameworks and model providers."
  }'
```

Response:

```json
{
  "document_id": "a1b2c3d4-...",
  "chunk_count": 1,
  "status": "ingested"
}
```

### Ask a question

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is MCP?", "top_k": 5}'
```

Response:

```json
{
  "answer": "MCP (Model Context Protocol) is an open standard for connecting AI models to external data sources and tools...",
  "citations": [],
  "trace_id": "e5f6g7h8-..."
}
```
