# Recipe: Memory Assistant

**Status:** Skeleton (design intent)

**Composes:**

- Pattern: [Memory](../patterns/memory.md)
- Framework (Py): [LangGraph](../frameworks/langgraph.md) (checkpointer + external memory store)
- Framework (TS): [Vercel AI SDK](../frameworks/vercel-ai-sdk.md) (manual memory integration)
- Stack: [FastAPI](../stack/api-fastapi.md) / [Hono](../stack/api-hono.md), [Postgres](../stack/relational-postgres.md), [Redis](../stack/cache-redis.md), [Qdrant](../stack/vector-qdrant.md), [Langfuse](../stack/tracing-langfuse.md)
- Cross-cutting: [Auth](../cross-cutting/auth-jwt.md), [Logging](../cross-cutting/logging-structured.md), [Observability](../cross-cutting/observability.md), [Rate limiting](../cross-cutting/rate-limiting.md)

## What it does

A conversational assistant that remembers facts, preferences, and context from previous interactions. Users can chat naturally, and the agent automatically extracts and stores noteworthy information. On subsequent conversations, relevant memories are retrieved and injected into the prompt, enabling personalized and contextually aware responses.

This implements **hybrid memory** — both explicit ("remember that I prefer dark mode") and implicit (agent automatically extracts key facts) memory, stored in a vector DB for semantic retrieval.

## Architecture

```
User message
    |
    v
┌──────────────────────────────────────┐
│           LangGraph State            │
│                                      │
│   [Retrieve memories] ──> relevant   │
│       │                  memories    │
│       v                              │
│   [Augment prompt] ──> system prompt │
│       │              + memories      │
│       v                              │
│   [Generate response]                │
│       │                              │
│       v                              │
│   [Extract new memories] ──> store   │
│       │                              │
│       v                              │
│   [Update memory store]              │
└──────────────────────────────────────┘
    |
    v
Response (memory-informed)
```

## Intended key files

### Python track

| File | Role |
|------|------|
| `app/agent/graph.py` | LangGraph state graph: retrieve → augment → generate → extract → store |
| `app/agent/memory_retriever.py` | Queries Qdrant for memories relevant to current message |
| `app/agent/memory_extractor.py` | Extracts new facts/preferences from the conversation |
| `app/models/schemas.py` | `Memory`, `MemoryType`, `ConversationState` schemas |
| `app/tools/memory_store.py` | Qdrant-backed memory CRUD (create, search, update, delete) |
| `app/api/chat.py` | `/chat` endpoint — accepts message + user_id, returns response |

## Example interaction

### First conversation

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user-123", "message": "I am a backend engineer working mostly with Go and Python"}'
```

Response: `"Nice to meet you! I'll keep in mind that you work with Go and Python..."`

### Later conversation

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user-123", "message": "What language should I use for this new microservice?"}'
```

Response: `"Since you work primarily with Go and Python, I'd suggest Go for a performance-critical microservice..."` (informed by retrieved memory)

## Design intent

- **LangGraph for stateful memory flow:** The retrieve → augment → generate → extract → store cycle is a natural graph. LangGraph's checkpointer preserves conversation state across API calls.
- **Qdrant for semantic memory search:** Memories are embedded and stored in Qdrant, enabling similarity-based retrieval. "What languages does this user know?" retrieves the Go/Python memory even if the query wording differs.
- **Scoped by user_id:** All memory operations are filtered by user ID. No cross-user memory leakage.
- **Memory deduplication:** The extractor checks for existing memories before creating new ones. If a user updates their preference, the old memory is updated rather than duplicated.
- **Relevance threshold:** Only memories above a similarity threshold are injected into the prompt. Prevents irrelevant memories from confusing the model.
