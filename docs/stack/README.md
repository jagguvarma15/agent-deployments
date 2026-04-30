# Stack

Infrastructure components used across prototypes. Each file answers: **"What do I run it on?"**

| Component | Choice | Role |
|-----------|--------|------|
| [LLM](llm-claude.md) | Claude (Sonnet / Haiku) | Primary language model |
| [API (Python)](api-fastapi.md) | FastAPI + Uvicorn | Python HTTP layer |
| [API (TypeScript)](api-hono.md) | Hono | TypeScript HTTP layer |
| [Vector DB](vector-qdrant.md) | Qdrant | Embedding storage and similarity search |
| [Relational DB](relational-postgres.md) | Postgres 16 | Persistent storage, session data |
| [Cache](cache-redis.md) | Redis 7 | Caching, rate limiting backend |
| [Tracing](tracing-langfuse.md) | Langfuse | LLM observability and tracing |
| [Eval](eval-deepeval-ragas-promptfoo.md) | DeepEval + RAGAS + Promptfoo | Evaluation and red-teaming |
| [Tool Protocol](tool-protocol-mcp.md) | MCP | Standardized tool interface |

## Shared infrastructure

All prototypes share a base `docker-compose.yml` that provides Postgres, Redis, and Langfuse. Each prototype extends this with its own services.
