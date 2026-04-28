# Recipe: docs-rag-qa

**Status:** Fully implemented (both tracks)

**Composes:**

- Pattern: [RAG](../patterns/rag.md)
- Framework (Py): [Pydantic AI](../frameworks/pydantic-ai.md) (agentic RAG with tool-based retrieval)
- Framework (TS): [Vercel AI SDK](../frameworks/vercel-ai-sdk.md) (tool-based retrieval via `generateText`)
- Stack: [FastAPI](../stack/api-fastapi.md) / [Hono](../stack/api-hono.md), [Postgres](../stack/relational-postgres.md), [Redis](../stack/cache-redis.md), [Qdrant](../stack/vector-qdrant.md), [Langfuse](../stack/tracing-langfuse.md)
- Cross-cutting: [Auth](../cross-cutting/auth-jwt.md), [Logging](../cross-cutting/logging-structured.md), [Observability](../cross-cutting/observability.md), [Rate limiting](../cross-cutting/rate-limiting.md)

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

## Key files

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

## Run locally

```bash
cd prototypes/docs-rag-qa/python   # or typescript
cp .env.example .env
# Add ANTHROPIC_API_KEY to .env
docker compose up
```

Or from repo root:

```bash
make up PROTOTYPE=docs-rag-qa TRACK=python
```

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

## Eval setup

- **Dataset:** `eval/dataset.jsonl` -- golden Q&A pairs with expected answers
- **Unit tests:** `tests/unit/` -- test chunker logic, schema validation, API routes (mocked agent)
- **Integration tests:** `tests/integration/` -- test full pipeline with real LLM (requires `ANTHROPIC_API_KEY`)
- **Eval metrics:** Faithfulness, answer relevancy, context recall (via DeepEval / RAGAS)
- **Security scan:** `eval/promptfoo.yaml` -- jailbreak and prompt injection tests

```bash
make test PROTOTYPE=docs-rag-qa TRACK=python       # unit + integration
make eval PROTOTYPE=docs-rag-qa TRACK=python        # eval suite
make security PROTOTYPE=docs-rag-qa                 # promptfoo red-team
```

## Design decisions

- **Agentic RAG over naive RAG:** The LLM decides when to retrieve, enabling multi-turn refinement. Trade-off: slightly higher latency from the tool-call round trip.
- **In-memory retriever as default:** Keeps `make up` instant with no embedding model dependency. Production swap: point `QDRANT_URL` at a real Qdrant instance and replace `retriever.py` with Qdrant client calls.
- **Pydantic AI over LangGraph (Python):** For a single-agent RAG pipeline, Pydantic AI's tool decorator is simpler than a LangGraph state graph. LangGraph becomes the better choice if you add multi-step retrieval, re-ranking, or human-in-the-loop.
- **Vercel AI SDK over Mastra (TypeScript):** The `generateText` + `tool()` pattern is clean and minimal for this use case. Mastra would add value if you needed built-in RAG primitives or workflow orchestration.
