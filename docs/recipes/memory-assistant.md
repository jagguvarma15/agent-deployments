# Recipe: Memory Assistant

**Status:** Blueprint (design spec)

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

## Data Models

### Python (Pydantic)

```python
from enum import Enum
from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    fact = "fact"           # "User works with Go and Python"
    preference = "preference"  # "User prefers dark mode"
    context = "context"     # "User is building a microservice"
    instruction = "instruction"  # "Always respond in bullet points"


class Memory(BaseModel):
    """A single memory entry."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    content: str = Field(..., min_length=1, description="The memory text")
    memory_type: MemoryType
    importance: float = Field(default=0.5, ge=0.0, le=1.0, description="How important this memory is")
    source_message: str | None = Field(default=None, description="The message this memory was extracted from")
    created_at: str | None = None
    last_accessed: str | None = None


class ExtractedMemories(BaseModel):
    """Output from the memory extraction step."""
    memories: list[Memory] = Field(default_factory=list)
    updates: list[dict] = Field(default_factory=list, description="Existing memories to update")


class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    response: str
    memories_used: int = Field(default=0, description="Number of memories injected into context")
    memories_created: int = Field(default=0, description="New memories extracted from this turn")
    trace_id: str


class ConversationState(BaseModel):
    """LangGraph state for the memory-augmented conversation."""
    user_id: str
    message: str
    retrieved_memories: list[Memory] = Field(default_factory=list)
    augmented_prompt: str = ""
    response: str = ""
    extracted_memories: list[Memory] = Field(default_factory=list)
```

### TypeScript (Zod)

```typescript
import { z } from "zod";

export const MemoryType = z.enum(["fact", "preference", "context", "instruction"]);
export type MemoryType = z.infer<typeof MemoryType>;

export const Memory = z.object({
  id: z.string(),
  user_id: z.string(),
  content: z.string().min(1),
  memory_type: MemoryType,
  importance: z.number().min(0).max(1).default(0.5),
  source_message: z.string().optional(),
  created_at: z.string().optional(),
  last_accessed: z.string().optional(),
});
export type Memory = z.infer<typeof Memory>;

export const ChatRequest = z.object({
  user_id: z.string().min(1),
  message: z.string().min(1),
});
export type ChatRequest = z.infer<typeof ChatRequest>;

export const ChatResponse = z.object({
  response: z.string(),
  memories_used: z.number().default(0),
  memories_created: z.number().default(0),
  trace_id: z.string(),
});
export type ChatResponse = z.infer<typeof ChatResponse>;
```

### LangGraph State (TypedDict)

```python
from typing import TypedDict

class MemoryGraphState(TypedDict):
    user_id: str
    message: str
    retrieved_memories: list[dict]
    augmented_system_prompt: str
    response: str
    extracted_memories: list[dict]
    memories_used_count: int
    memories_created_count: int
```

## API Contract

### `POST /chat`

Send a message to the memory-augmented assistant.

**Request:**

```json
{
  "user_id": "user-123",
  "message": "I am a backend engineer working mostly with Go and Python"
}
```

**Response (200):**

```json
{
  "response": "Nice to meet you! I'll keep in mind that you work with Go and Python. What are you working on?",
  "memories_used": 0,
  "memories_created": 2,
  "trace_id": "d4e5f6a7-b8c9-0123-def0-456789012345"
}
```

**Subsequent request:**

```json
{
  "user_id": "user-123",
  "message": "What language should I use for this new microservice?"
}
```

**Subsequent response (200):**

```json
{
  "response": "Since you work primarily with Go and Python, I'd suggest Go for a performance-critical microservice — its concurrency model and low memory footprint are ideal. Python would be better if you need rapid prototyping or heavy data processing.",
  "memories_used": 2,
  "memories_created": 1,
  "trace_id": "e5f6a7b8-c9d0-1234-ef01-567890123456"
}
```

**Errors:**

| Status | Body | When |
|--------|------|------|
| 400 | `{"error": "Invalid request", "details": [...]}` | Missing user_id or message |
| 500 | `{"error": "Chat failed"}` | LLM or memory store error |

### `GET /memories/{user_id}`

Retrieve stored memories for a user (admin/debug endpoint).

**Response (200):**

```json
{
  "memories": [
    {"id": "mem-1", "content": "Works with Go and Python", "memory_type": "fact", "importance": 0.8},
    {"id": "mem-2", "content": "Is a backend engineer", "memory_type": "fact", "importance": 0.7}
  ],
  "total": 2
}
```

### `DELETE /memories/{user_id}`

Clear all memories for a user.

### `GET /health`

Returns `{"status": "ok"}`.

## Tool Specifications

### `search_memories`

| Field | Value |
|-------|-------|
| **Description** | Search the user's memory store for memories relevant to the current message. Uses semantic similarity via Qdrant. |
| **Parameters** | `query` (string, required) — Search text. `user_id` (string, required) — Scope to this user. `top_k` (int, optional) — Max results, default 5. `threshold` (float, optional) — Minimum similarity score, default 0.7. |
| **Return type** | `list[Memory]` — Matching memories above the similarity threshold. |

### `store_memory`

| Field | Value |
|-------|-------|
| **Description** | Store a new memory in Qdrant, or update an existing memory if a near-duplicate exists. |
| **Parameters** | `memory` (Memory, required) — The memory to store. |
| **Return type** | `string` — "created" or "updated:{existing_id}". |

### `delete_memory`

| Field | Value |
|-------|-------|
| **Description** | Delete a specific memory by ID. |
| **Parameters** | `memory_id` (string, required). `user_id` (string, required) — For authorization check. |
| **Return type** | `string` — "deleted" or "not_found". |

## Prompt Specifications

### Conversation system prompt (augmented with memories)

```
You are a helpful assistant with memory. You remember facts, preferences,
and context from previous conversations with this user.

{memory_block}

Use these memories naturally in your responses — reference them when relevant,
but don't awkwardly force them in. If the user tells you something new about
themselves, acknowledge it naturally.

If you don't have relevant memories, respond based on the current message alone.
Never fabricate memories you don't have.
```

Where `{memory_block}` is dynamically constructed:

```
## What I remember about you:
- You work with Go and Python (fact, importance: 0.8)
- You are a backend engineer (fact, importance: 0.7)
- You prefer concise code examples (preference, importance: 0.6)
```

**Design rationale:**
- **"Don't awkwardly force them in"** — Without this, the model references memories in every response regardless of relevance: "Since you're a Go developer, here's a weather update..."
- **"Never fabricate memories"** — Prevents the model from inventing past interactions.
- **Importance scores visible** — Lets the model weigh which memories are most worth referencing.

### Memory extraction prompt

```
Analyze this conversation turn and extract any new information worth remembering.

User message: {message}
Assistant response: {response}

Extract memories in these categories:
- fact: concrete information about the user (role, skills, projects)
- preference: stated or implied preferences (tools, styles, communication)
- context: current situation or ongoing work
- instruction: explicit requests about how to behave

Rules:
1. Only extract genuinely noteworthy information
2. Skip pleasantries and small talk
3. If this updates an existing memory, flag it as an update
4. Rate importance from 0.0 (trivial) to 1.0 (critical identity fact)
5. Be concise — memories should be one sentence

Return an empty list if there's nothing worth remembering.
```

**Design rationale:**
- **"Only extract genuinely noteworthy information"** — Without this, the extractor stores every detail: "User said hello at 3pm."
- **"Skip pleasantries"** — Prevents memory pollution from "how are you?" exchanges.
- **Update vs create** — Deduplication is critical. "I now work with Rust" should update "works with Go and Python," not create a separate memory.

## Key files

### Python track

| File | Role |
|------|------|
| `app/main.py` | FastAPI entrypoint with lifespan, routers, health check |
| `app/settings.py` | Config: model, Qdrant collection, similarity threshold |
| `app/models/schemas.py` | All Pydantic models and LangGraph state TypedDict |
| `app/agent/graph.py` | LangGraph state graph: retrieve → augment → generate → extract → store |
| `app/agent/memory_retriever.py` | Queries Qdrant for memories relevant to current message |
| `app/agent/memory_extractor.py` | Extracts new facts/preferences from the conversation |
| `app/tools/memory_store.py` | Qdrant-backed memory CRUD (create, search, update, delete) |
| `app/api/chat.py` | `/chat` endpoint — accepts message + user_id, returns response |
| `app/api/memories.py` | `/memories/{user_id}` — debug endpoint for viewing/clearing memories |

### TypeScript track

| File | Role |
|------|------|
| `src/index.ts` | Hono entrypoint with routes and health check |
| `src/config.ts` | Zod-validated env config |
| `src/schemas/index.ts` | All Zod schemas |
| `src/agent/chat.ts` | Memory-augmented chat: retrieve → augment → generate → extract → store |
| `src/agent/memory-retriever.ts` | Qdrant semantic search for relevant memories |
| `src/agent/memory-extractor.ts` | `generateObject()` to extract memories from conversation |
| `src/tools/memory-store.ts` | Qdrant client: store, search, update, delete memories |
| `src/api/chat.ts` | `/chat` route handler |
| `src/api/memories.ts` | `/memories/:userId` debug route |

## Implementation Roadmap

| Step | Task | Key deliverables |
|------|------|-----------------|
| 1 | **Project scaffolding** | FastAPI/Hono app with `/health`, settings, structured logging |
| 2 | **Data models** | All Pydantic + Zod schemas, LangGraph state TypedDict |
| 3 | **Qdrant memory store** | CRUD operations: store, search (semantic), update, delete. User-scoped. |
| 4 | **Memory retriever node** | Query Qdrant with message text, filter by user_id and threshold |
| 5 | **Prompt augmentation** | Build `{memory_block}` from retrieved memories, inject into system prompt |
| 6 | **Response generation** | Agent call with augmented prompt |
| 7 | **Memory extractor node** | Analyze conversation turn, extract new memories with type and importance |
| 8 | **Memory deduplication** | Check for near-duplicates before storing; update existing if found |
| 9 | **LangGraph wiring** | State graph: retrieve → augment → generate → extract → store |
| 10 | **API endpoints** | `POST /chat`, `GET /memories/{user_id}`, `DELETE /memories/{user_id}` |
| 11 | **Cross-cutting** | JWT auth, rate limiting, Langfuse tracing per node |
| 12 | **Unit tests** | Memory store CRUD, retriever threshold, extractor output validation |
| 13 | **Integration + eval** | Multi-turn conversation with real LLM, verify memory recall |

## Environment & Deployment

### Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `CHAT_MODEL` | No | `claude-sonnet-4-6-20250514` | Model for conversation |
| `EXTRACTOR_MODEL` | No | `claude-haiku-4-5-20251001` | Model for memory extraction (cheaper) |
| `DATABASE_URL` | No | `postgresql+asyncpg://agent:agent@localhost:5432/agent_db` | Postgres connection |
| `REDIS_URL` | No | `redis://localhost:6379` | Redis for rate limiting |
| `QDRANT_URL` | No | `http://localhost:6333` | Qdrant vector DB URL |
| `QDRANT_COLLECTION` | No | `memories` | Qdrant collection name |
| `MEMORY_SIMILARITY_THRESHOLD` | No | `0.7` | Minimum similarity score for memory retrieval |
| `MEMORY_TOP_K` | No | `5` | Max memories to retrieve per turn |
| `LANGFUSE_PUBLIC_KEY` | No | `pk-lf-local` | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | No | `sk-lf-local` | Langfuse secret key |
| `LANGFUSE_HOST` | No | `http://localhost:3000` | Langfuse server URL |
| `JWT_SECRET` | No | `change-me-in-production` | JWT signing secret |
| `APP_ENV` | No | `development` | Environment name |
| `LOG_LEVEL` | No | `INFO` | Log level |

### Docker Compose

See [Docker Compose template](../reference/docker-compose-template.md) for base infrastructure. This agent needs: Postgres, Redis, **Qdrant**, Langfuse.

## Test Strategy

### Unit tests

```python
def test_memory_scoped_by_user():
    """Memories from user-A are not returned for user-B."""
    store_memory(Memory(user_id="A", content="fact A", memory_type="fact"))
    results = search_memories(query="fact", user_id="B")
    assert len(results) == 0

def test_memory_deduplication():
    """Storing a near-duplicate updates the existing memory instead of creating a new one."""
    store_memory(Memory(user_id="A", content="works with Python", memory_type="fact"))
    store_memory(Memory(user_id="A", content="works with Python and Go", memory_type="fact"))
    all_memories = get_all_memories(user_id="A")
    assert len(all_memories) == 1
    assert "Go" in all_memories[0].content

def test_similarity_threshold():
    """Memories below the threshold are not returned."""
    store_memory(Memory(user_id="A", content="likes dark mode", memory_type="preference"))
    results = search_memories(query="quantum physics", user_id="A", threshold=0.7)
    assert len(results) == 0

def test_extraction_skips_pleasantries(mock_llm_client):
    """Extractor returns empty list for 'hello how are you' messages."""
    memories = extract_memories("Hello!", "Hi there! How can I help?")
    assert len(memories) == 0
```

### Integration tests (main branch only)

```python
async def test_memory_persists_across_turns():
    """Information from turn 1 is used in turn 2."""
    # Turn 1: tell the agent something
    r1 = await client.post("/chat", json={
        "user_id": "test-user",
        "message": "I'm a data scientist who works with PyTorch"
    })
    assert r1.json()["memories_created"] >= 1

    # Turn 2: ask a question that should trigger memory recall
    r2 = await client.post("/chat", json={
        "user_id": "test-user",
        "message": "What framework should I use for my next ML project?"
    })
    assert r2.json()["memories_used"] >= 1
    assert "pytorch" in r2.json()["response"].lower()
```

### Eval assertions

- Memory from turn N is retrievable in turn N+1
- User-A's memories never leak into user-B's responses
- "Remember that X" → memory created with type "instruction" or "preference"
- "Forget that" or "delete my data" → memories cleared (privacy compliance)
- Agent references memories naturally, not mechanically

## Eval Dataset

```jsonl
{"turns": [{"message": "I'm a Go developer", "expect_memories_created": 1}, {"message": "What language should I use?", "expect_memory_recall": true, "expect_mention": "Go"}]}
{"turns": [{"message": "Remember that I prefer bullet point answers", "expect_memories_created": 1, "expect_type": "instruction"}, {"message": "Explain Docker", "expect_format": "bullet_points"}]}
{"turns": [{"message": "I work at Acme Corp on the payments team", "expect_memories_created": 2}, {"message": "What should I name my new service?", "expect_memory_recall": true}]}
{"turns": [{"message": "Hello!", "expect_memories_created": 0}]}
{"turns": [{"message": "I used to work with Java but now I use Rust", "expect_memory_update": true}]}
```

## Design decisions

- **LangGraph for stateful memory flow:** The retrieve → augment → generate → extract → store cycle is a natural graph. LangGraph's checkpointer preserves conversation state across API calls.
- **Qdrant for semantic memory search:** Memories are embedded and stored in Qdrant, enabling similarity-based retrieval. "What languages does this user know?" retrieves the Go/Python memory even if the query wording differs.
- **Scoped by user_id:** All memory operations are filtered by user ID. No cross-user memory leakage.
- **Memory deduplication:** The extractor checks for existing memories before creating new ones. If a user updates their preference, the old memory is updated rather than duplicated.
- **Relevance threshold:** Only memories above a similarity threshold are injected into the prompt. Prevents irrelevant memories from confusing the model.
- **Separate extraction model:** Memory extraction uses a cheaper model (Haiku) since it's a simpler classification task. The conversation itself uses the more capable model.
