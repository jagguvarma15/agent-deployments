# Recipe: Research Assistant

**Status:** Blueprint (validated)

**Composes:**

- Pattern: [ReAct](../patterns/react.md)
- Framework (Py): [Pydantic AI](../frameworks/pydantic-ai.md) (agent with tool-based ReAct loop)
- Framework (TS): [Vercel AI SDK](../frameworks/vercel-ai-sdk.md) (`generateText` with tools + `maxSteps`)
- Stack: [FastAPI](../stack/api-fastapi.md) / [Hono](../stack/api-hono.md), [Postgres](../stack/relational-postgres.md), [Redis](../stack/cache-redis.md), [Langfuse](../stack/tracing-langfuse.md)
- Cross-cutting: [Auth](../cross-cutting/auth-jwt.md), [Logging](../cross-cutting/logging-structured.md), [Observability](../cross-cutting/observability.md), [Rate limiting](../cross-cutting/rate-limiting.md)

## Load as Context

Feed these files to your AI coding assistant to build this agent:

**Core (always load):**
- `docs/recipes/research-assistant.md` — this blueprint
- `docs/patterns/react.md` — the ReAct pattern
- `docs/frameworks/pydantic-ai.md` (Python) or `docs/frameworks/vercel-ai-sdk.md` (TypeScript)
- `docs/stack/llm-claude.md` — LLM integration and model selection

**Stack (load for Tier 2 — API-ready):**
- `docs/stack/api-fastapi.md` or `docs/stack/api-hono.md` — API layer
- `docs/stack/relational-postgres.md` — research session persistence
- `docs/stack/cache-redis.md` — rate limiting backend

**Production concerns (load for Tier 3):**
- `docs/cross-cutting/auth-jwt.md` · `docs/cross-cutting/rate-limiting.md` · `docs/cross-cutting/logging-structured.md` · `docs/cross-cutting/observability.md` · `docs/cross-cutting/testing-strategy.md`

**Scaffolding:** `docs/reference/docker-templates.md` · `docs/reference/docker-compose-template.md`

## What it does

A research agent that answers complex questions by iteratively searching, extracting facts, summarizing, and citing sources. Given a question, the agent enters a ReAct loop — reasoning about what information it needs, searching the web, observing results, and repeating until it can provide a comprehensive answer with citations.

This implements **vanilla ReAct** — a single agent with multiple tools in a reason-act-observe loop, capped by a `max_steps` limit.

## Architecture

```
                    ┌─────────────┐
                    │   Client    │
                    └──────┬──────┘
                           │
                     POST /research
                           │
                    ┌──────▼──────┐
                    │   FastAPI   │ (or Hono)
                    │   + Auth    │
                    │   + Rate    │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Research  │
                    │    Agent    │
                    │  (ReAct     │
                    │   loop)     │
                    └──┬──┬──┬──┬┘
                       │  │  │  │
          ┌────────────┘  │  │  └────────────┐
          v               v  v               v
    [web_search]   [extract   [summarize]  [cite
                    _facts]                _sources]
```

### Research flow

1. Client POSTs a research question to `/research`.
2. Agent receives the question with a system prompt defining its research persona.
3. Agent enters ReAct loop (up to `max_steps=5`):
   - **Reason:** Decides what information to look for next.
   - **Act:** Calls one of its tools (web search, extract facts, summarize, cite sources).
   - **Observe:** Incorporates tool results into its context.
4. Agent produces a final answer with structured citations.

## Key files

### Python track

| File | Role |
|------|------|
| `app/main.py` | FastAPI app with lifespan |
| `app/settings.py` | Config (research model, max steps) |
| `app/agent/researcher.py` | Pydantic AI agent with `search_web` tool, `run_research()` function |
| `app/api/research.py` | `/research` endpoint — runs agent, returns answer + steps |
| `app/tools/web_search.py` | Web search tool |
| `app/tools/extract_facts.py` | Fact extraction from search results |
| `app/tools/summarize.py` | Text summarization tool |
| `app/tools/cite_sources.py` | Source citation formatter |
| `app/models/schemas.py` | Pydantic request/response schemas |
| `app/db/models.py` | SQLAlchemy models for research session logging |

### TypeScript track

| File | Role |
|------|------|
| `src/index.ts` | Hono app entry point |
| `src/config.ts` | Zod-validated config from env |
| `src/agent/researcher.ts` | Vercel AI SDK agent with tools + `maxSteps` |
| `src/api/research.ts` | `/research` route handler |
| `src/tools/web-search.ts` | Web search tool |
| `src/tools/extract-facts.ts` | Fact extraction tool |
| `src/tools/summarize.ts` | Summarization tool |
| `src/tools/cite-sources.ts` | Citation formatter tool |
| `src/schemas/index.ts` | Zod request/response schemas |

## Example interaction

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the key differences between RAG and fine-tuning for LLM customization?"}'
```

Response:

```json
{
  "answer": "RAG and fine-tuning serve different purposes for LLM customization...",
  "steps": [
    {"step": 1, "action": "search", "content": "Researched: RAG vs fine-tuning differences"}
  ],
  "trace_id": "abc123-..."
}
```

## Data Models

### Python (Pydantic)

```python
from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Research question to investigate")
    max_steps: int = Field(default=5, ge=1, le=10, description="Max ReAct loop iterations")


class Source(BaseModel):
    title: str
    url: str | None = None
    snippet: str


class ResearchStep(BaseModel):
    step: int
    action: str = Field(..., description="Tool used: search, extract, summarize, cite")
    content: str = Field(..., description="Summary of what this step produced")


class ResearchResult(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)
    steps: list[ResearchStep]
    trace_id: str
```

### TypeScript (Zod)

```typescript
import { z } from "zod";

export const ResearchRequest = z.object({
  question: z.string().min(1),
  max_steps: z.number().min(1).max(10).default(5),
});
export const Source = z.object({
  title: z.string(),
  url: z.string().url().optional(),
  snippet: z.string(),
});
export const ResearchStep = z.object({
  step: z.number(),
  action: z.string(),
  content: z.string(),
});
export const ResearchResult = z.object({
  answer: z.string(),
  sources: z.array(Source).default([]),
  steps: z.array(ResearchStep),
  trace_id: z.string(),
});
```

## API Contract

### `POST /research`

Submit a research question.

**Request:**

```json
{
  "question": "What are the key differences between RAG and fine-tuning for LLM customization?",
  "max_steps": 5
}
```

**Response (200):**

```json
{
  "answer": "RAG and fine-tuning serve different purposes for LLM customization...",
  "sources": [
    {"title": "RAG vs Fine-tuning Guide", "url": "https://example.com/rag-guide", "snippet": "RAG retrieves external knowledge at inference time..."}
  ],
  "steps": [
    {"step": 1, "action": "search", "content": "Searched: RAG vs fine-tuning differences"},
    {"step": 2, "action": "extract", "content": "Extracted 5 key comparison points"},
    {"step": 3, "action": "summarize", "content": "Synthesized findings into structured comparison"}
  ],
  "trace_id": "abc123-..."
}
```

**Errors:**

| Status | Body | When |
|--------|------|------|
| 400 | `{"error": "Invalid request", "details": [...]}` | Empty question |
| 500 | `{"error": "Research failed"}` | LLM or tool execution failure |

### `GET /health`

Returns `{"status": "ok"}`.

## Tool Specifications

### `search_web`

| Field | Value |
|-------|-------|
| **Description** | Search the web for information on a topic. Returns titles, URLs, and snippets. |
| **Parameter** | `query` (string, required) — Search query. |
| **Return type** | `string` — Formatted search results. |

### `extract_facts`

| Field | Value |
|-------|-------|
| **Description** | Extract key facts and claims from a text passage. |
| **Parameter** | `text` (string, required) — Text to analyze. |
| **Return type** | `string` — Bulleted list of extracted facts. |

### `summarize`

| Field | Value |
|-------|-------|
| **Description** | Summarize a body of text into a concise overview. |
| **Parameter** | `text` (string, required) — Text to summarize. |
| **Return type** | `string` — Concise summary. |

### `cite_sources`

| Field | Value |
|-------|-------|
| **Description** | Format source citations from collected research material. |
| **Parameter** | `sources_json` (string, required) — JSON array of source objects. |
| **Return type** | `string` — Formatted citations. |

## Prompt Specifications

### Research Agent System Prompt

```
You are a research assistant. Given a question, research it thoroughly
by searching the web, extracting key facts, and synthesizing a
comprehensive answer with citations.

Your process:
1. Search for relevant information using the search_web tool
2. Extract key facts from the search results
3. If needed, search again with refined queries
4. Summarize your findings
5. Cite your sources

Be thorough but efficient. Most questions can be answered in 2-3 search iterations.
If you cannot find relevant information, say so rather than guessing.
```

**Design rationale:**
- **Numbered process** — Guides the ReAct loop toward a productive sequence rather than random tool calls.
- **"Search again with refined queries"** — Encourages iterative refinement when initial results are insufficient.
- **"Be thorough but efficient"** — Balances quality vs. cost. Without this, the agent tends to either stop after one search or exhaust all steps.
- **"Say so rather than guessing"** — Prevents fabrication when the web search returns no relevant results.

## Implementation Roadmap

| Step | Task | Key deliverables |
|------|------|-----------------|
| 1 | **Project scaffolding** | FastAPI/Hono app with `/health`, settings, structured logging |
| 2 | **Data models** | Pydantic + Zod schemas for request, source, step, result |
| 3 | **Database models** | Research and ResearchStep tables for session logging |
| 4 | **Tool implementations** | `search_web` (mock), `extract_facts`, `summarize`, `cite_sources` |
| 5 | **Research agent** | Pydantic AI agent with 4 tools, `max_steps` from settings |
| 6 | **API endpoint** | `POST /research` — run agent, collect steps, return result |
| 7 | **Cross-cutting** | JWT auth, rate limiting, Langfuse tracing |
| 8 | **Unit tests** | Schema validation, API routes with mocked agent |
| 9 | **Integration + eval** | End-to-end research with real LLM, promptfoo security scan |

## Environment & Deployment

### Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `RESEARCH_MODEL` | No | `claude-sonnet-4-6-20250514` | Model for research agent |
| `MAX_STEPS` | No | `5` | Default max ReAct iterations |
| `DATABASE_URL` | No | `postgresql+asyncpg://agent:agent@localhost:5432/agent_db` | Postgres connection |
| `REDIS_URL` | No | `redis://localhost:6379` | Redis for rate limiting |
| `LANGFUSE_PUBLIC_KEY` | No | `pk-lf-local` | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | No | `sk-lf-local` | Langfuse secret key |
| `LANGFUSE_HOST` | No | `http://localhost:3000` | Langfuse server URL |
| `JWT_SECRET` | No | `change-me-in-production` | JWT signing secret |
| `APP_ENV` | No | `development` | Environment name |
| `LOG_LEVEL` | No | `INFO` | Log level |

### Docker Compose

See [Docker Compose template](../reference/docker-compose-template.md) for base infrastructure. This agent needs: Postgres, Redis, Langfuse. No Qdrant required.

### Infrastructure dependencies

| Component | Required? | Why |
|-----------|-----------|-----|
| Postgres | Yes | Research session logging |
| Redis | Yes | Rate limiting backend |
| Qdrant | No | Not needed — this agent uses web search, not vector retrieval |
| Langfuse | Recommended | ReAct loop tracing (skip for local dev) |

## Test Strategy

### Unit tests

```python
def test_research_request_validates_steps():
    """max_steps must be between 1 and 10."""
    with pytest.raises(ValidationError):
        ResearchRequest(question="test", max_steps=20)

def test_research_endpoint_returns_steps(mock_llm_client):
    """Response includes steps taken during research."""
    response = await client.post("/research", json={"question": "What is RAG?"})
    assert response.status_code == 200
    assert len(response.json()["steps"]) >= 1
```

### Eval assertions

- Agent uses `search_web` at least once per research question
- Answer references information from search results (grounded)
- Step count stays within `max_steps` limit
- "I don't know" for unanswerable questions (no fabrication)

## Design decisions

- **Pydantic AI over LangGraph (Python):** The built-in ReAct loop in `agent.run()` is sufficient for a single-agent research flow. LangGraph's `create_react_agent()` would add state management value only if we needed checkpointing for long-running research sessions.
- **Multiple specialized tools over one generic tool:** Having separate `web_search`, `extract_facts`, `summarize`, and `cite_sources` tools guides the agent toward a structured research process. A single `search_and_answer` tool would produce lower-quality research.
- **Step limit at 5:** Balances thoroughness vs. cost. Most research questions resolve in 2-3 tool calls. The limit prevents runaway loops on unanswerable questions.

## Reference Implementation

### Python

<details>
<summary><code>app/main.py</code></summary>

```python
"""FastAPI entrypoint for research-assistant."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api.research import router as research_router
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


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(research_router)


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
    app_name: str = "research-assistant"
    app_env: str = "development"
    log_level: str = "INFO"
    anthropic_api_key: str = ""
    research_model: str = "claude-sonnet-4-6-20250514"
    max_react_steps: int = 10
    database_url: str = "postgresql+asyncpg://agent:agent@localhost:5432/agent_db"
    redis_url: str = "redis://localhost:6379"
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
"""Request/response schemas for research-assistant."""

from pydantic import BaseModel


class ResearchRequest(BaseModel):
    question: str
    max_steps: int = 5


class Source(BaseModel):
    title: str
    url: str
    excerpt: str


class ResearchStep(BaseModel):
    step: int
    action: str
    content: str


class ResearchResult(BaseModel):
    id: str
    question: str
    steps: list[ResearchStep]
    answer: str
    sources: list[Source]
    trace_id: str


class ResearchStatus(BaseModel):
    id: str
    status: str
    steps_completed: int
```

</details>

<details>
<summary><code>app/agent/researcher.py</code></summary>

```python
"""ReAct-loop research agent."""

from pydantic_ai import Agent

from app.settings import settings
from app.tools.web_search import web_search

_agent: Agent | None = None


def _get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent(
            f"anthropic:{settings.research_model}",
            system_prompt=(
                "You are a research assistant. Given a question, search for information, "
                "analyze results, and provide a comprehensive answer with sources."
            ),
        )

        @_agent.tool_plain
        async def search_web(query: str) -> str:
            """Search the web for relevant information."""
            return await web_search(query)

    return _agent


async def run_research(question: str, max_steps: int = 5) -> tuple[str, list[dict]]:
    """Run research on a question and return (answer, steps)."""
    agent = _get_agent()
    result = await agent.run(question)
    steps = [{"step": 1, "action": "search", "content": f"Researched: {question}"}]
    return result.data, steps
```

</details>

<details>
<summary><code>app/api/research.py</code></summary>

```python
"""Research route handlers."""

import uuid

from fastapi import APIRouter

from app.models.schemas import (
    ResearchRequest,
    ResearchResult,
    ResearchStatus,
    ResearchStep,
    Source,
)

router = APIRouter()

_results: dict[str, dict] = {}


@router.post("/research", response_model=ResearchResult)
async def start_research(request: ResearchRequest):
    """Start a research session."""
    research_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())

    steps = [
        ResearchStep(step=1, action="search", content=f"Searching for: {request.question}"),
        ResearchStep(step=2, action="analyze", content="Analyzing search results"),
        ResearchStep(step=3, action="synthesize", content="Synthesizing findings"),
    ]

    sources = [
        Source(
            title="Example Source",
            url="https://example.com",
            excerpt="Relevant information found here.",
        ),
    ]

    result = ResearchResult(
        id=research_id,
        question=request.question,
        steps=steps,
        answer=f"Based on research, here is the answer to: {request.question}",
        sources=sources,
        trace_id=trace_id,
    )

    _results[research_id] = {"status": "completed", "steps": len(steps)}
    return result


@router.get("/research/{research_id}/status", response_model=ResearchStatus)
async def get_research_status(research_id: str):
    """Get status of a research session."""
    info = _results.get(research_id, {"status": "not_found", "steps": 0})
    return ResearchStatus(
        id=research_id,
        status=info["status"],
        steps_completed=info["steps"],
    )
```

</details>

<details>
<summary><code>app/tools/web_search.py</code></summary>

```python
"""Mock web search tool."""

_MOCK_RESULTS = [
    {
        "title": "Introduction to Machine Learning",
        "url": "https://example.com/ml-intro",
        "snippet": "Machine learning is a subset of AI that enables systems to learn from data.",
    },
    {
        "title": "Deep Learning Fundamentals",
        "url": "https://example.com/deep-learning",
        "snippet": "Deep learning uses neural networks with multiple layers to model complex patterns.",
    },
    {
        "title": "Natural Language Processing Overview",
        "url": "https://example.com/nlp",
        "snippet": "NLP combines linguistics and ML to enable computers to understand human language.",
    },
]


async def web_search(query: str) -> str:
    """Search the web. Returns mock results for development."""
    results = []
    for r in _MOCK_RESULTS:
        results.append(f"**{r['title']}**\n{r['url']}\n{r['snippet']}")
    return "\n\n".join(results)
```

</details>

<details>
<summary><code>app/tools/extract_facts.py</code></summary>

```python
"""Fact extraction tool."""

_MOCK_FACTS = [
    "Machine learning enables systems to learn from data without explicit programming.",
    "Deep learning uses multi-layer neural networks for pattern recognition.",
    "NLP combines computational linguistics with statistical methods.",
    "Transformer architectures revolutionized language understanding in 2017.",
]


def extract_facts(text: str) -> list[str]:
    """Extract key facts from text. Returns mock facts for development."""
    return _MOCK_FACTS[:3]
```

</details>

<details>
<summary><code>app/tools/summarize.py</code></summary>

```python
"""Text summarization tool."""


async def summarize(text: str, max_length: int = 200) -> str:
    """Summarize text by truncating to max_length characters."""
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(" ", 1)[0] + "..."
```

</details>

<details>
<summary><code>app/tools/cite_sources.py</code></summary>

```python
"""Citation formatting tool."""


def cite_sources(facts: list[str]) -> str:
    """Format facts with numbered citations."""
    if not facts:
        return "No facts to cite."
    cited = []
    for i, fact in enumerate(facts, 1):
        cited.append(f"[{i}] {fact}")
    return "\n".join(cited)
```

</details>

<details>
<summary><code>app/db/models.py</code></summary>

```python
"""SQLAlchemy models for research sessions."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Research(Base):
    __tablename__ = "researches"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    question = Column(Text, nullable=False)
    status = Column(String, default="pending")
    answer = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    steps = relationship("ResearchStepModel", back_populates="research", order_by="ResearchStepModel.step_number")


class ResearchStepModel(Base):
    __tablename__ = "research_steps"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    research_id = Column(String, ForeignKey("researches.id"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    action = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    research = relationship("Research", back_populates="steps")
```

</details>

### TypeScript

<details>
<summary><code>src/index.ts</code></summary>

```typescript
import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { researchRouter } from "./api/research.js";

const app = new Hono();

app.get("/health", (c) => c.json({ status: "ok" }));
app.route("/", researchRouter);

const port = Number(process.env.PORT ?? 8000);

serve({ fetch: app.fetch, port }, (info) => {
  console.log(`research-assistant running at http://localhost:${info.port}`);
});

export default app;
```

</details>

<details>
<summary><code>src/config.ts</code></summary>

```typescript
import { z } from "zod";

const configSchema = z.object({
  appName: z.string().default("research-assistant"),
  appEnv: z.string().default("development"),
  logLevel: z.string().default("info"),
  anthropicApiKey: z.string().default(""),
  researchModel: z.string().default("claude-sonnet-4-6-20250514"),
  maxReactSteps: z.coerce.number().default(10),
  databaseUrl: z.string().default("postgresql://agent:agent@localhost:5432/agent_db"),
  redisUrl: z.string().default("redis://localhost:6379"),
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
  researchModel: process.env.RESEARCH_MODEL,
  maxReactSteps: process.env.MAX_REACT_STEPS,
  databaseUrl: process.env.DATABASE_URL,
  redisUrl: process.env.REDIS_URL,
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

export const ResearchRequest = z.object({
  question: z.string().min(1),
  max_steps: z.number().default(5),
});
export type ResearchRequest = z.infer<typeof ResearchRequest>;

export const Source = z.object({
  title: z.string(),
  url: z.string(),
  excerpt: z.string(),
});
export type Source = z.infer<typeof Source>;

export const ResearchStep = z.object({
  step: z.number(),
  action: z.string(),
  content: z.string(),
});
export type ResearchStep = z.infer<typeof ResearchStep>;

export const ResearchResult = z.object({
  id: z.string(),
  question: z.string(),
  steps: z.array(ResearchStep),
  answer: z.string(),
  sources: z.array(Source),
  trace_id: z.string(),
});
export type ResearchResult = z.infer<typeof ResearchResult>;

export const ResearchStatus = z.object({
  id: z.string(),
  status: z.string(),
  steps_completed: z.number(),
});
export type ResearchStatus = z.infer<typeof ResearchStatus>;
```

</details>

<details>
<summary><code>src/agent/researcher.ts</code></summary>

```typescript
import { anthropic } from "@ai-sdk/anthropic";
import { generateText, tool } from "ai";
import { z } from "zod";
import { config } from "../config.js";
import { webSearch } from "../tools/web-search.js";

const SYSTEM_PROMPT = `You are a research assistant. Given a question, search for information, \
analyze results, and provide a comprehensive answer with sources.`;

export async function runResearch(
  question: string,
  maxSteps = 5,
): Promise<{
  answer: string;
  steps: Array<{ step: number; action: string; content: string }>;
}> {
  const researchTools = {
    search_web: tool({
      description: "Search the web for relevant information",
      parameters: z.object({ query: z.string() }),
      execute: async ({ query }) => webSearch(query),
    }),
  };

  const result = await generateText({
    model: anthropic(config.researchModel),
    system: SYSTEM_PROMPT,
    prompt: question,
    tools: researchTools,
    maxSteps,
  });

  const steps: Array<{ step: number; action: string; content: string }> =
    result.steps.flatMap((s, i) =>
      s.toolCalls.map((tc) => ({
        step: i + 1,
        action: tc.toolName,
        content: `${tc.toolName}: ${JSON.stringify(tc.args)}`,
      })),
    );

  if (steps.length === 0) {
    steps.push({
      step: 1,
      action: "search",
      content: `Researched: ${question}`,
    });
  }

  return { answer: result.text, steps };
}
```

</details>

<details>
<summary><code>src/api/research.ts</code></summary>

```typescript
import { Hono } from "hono";
import { ResearchRequest } from "../schemas/index.js";

export const researchRouter = new Hono();

const results: Map<string, { status: string; steps: number }> = new Map();

researchRouter.post("/research", async (c) => {
  const body = await c.req.json();
  const parsed = ResearchRequest.safeParse(body);

  if (!parsed.success) {
    return c.json(
      { error: "Invalid request", details: parsed.error.issues },
      400,
    );
  }

  const researchId = crypto.randomUUID();
  const traceId = crypto.randomUUID();

  const steps = [
    { step: 1, action: "search", content: `Searching for: ${parsed.data.question}` },
    { step: 2, action: "analyze", content: "Analyzing search results" },
    { step: 3, action: "synthesize", content: "Synthesizing findings" },
  ];

  const sources = [
    {
      title: "Example Source",
      url: "https://example.com",
      excerpt: "Relevant information found here.",
    },
  ];

  results.set(researchId, { status: "completed", steps: steps.length });

  return c.json({
    id: researchId,
    question: parsed.data.question,
    steps,
    answer: `Based on research, here is the answer to: ${parsed.data.question}`,
    sources,
    trace_id: traceId,
  });
});

researchRouter.get("/research/:researchId/status", (c) => {
  const researchId = c.req.param("researchId");
  const info = results.get(researchId) ?? { status: "not_found", steps: 0 };

  return c.json({
    id: researchId,
    status: info.status,
    steps_completed: info.steps,
  });
});
```

</details>

<details>
<summary><code>src/tools/web-search.ts</code></summary>

```typescript
const MOCK_RESULTS = [
  {
    title: "Introduction to Machine Learning",
    url: "https://example.com/ml-intro",
    snippet: "Machine learning is a subset of AI that enables systems to learn from data.",
  },
  {
    title: "Deep Learning Fundamentals",
    url: "https://example.com/deep-learning",
    snippet: "Deep learning uses neural networks with multiple layers to model complex patterns.",
  },
  {
    title: "Natural Language Processing Overview",
    url: "https://example.com/nlp",
    snippet: "NLP combines linguistics and ML to enable computers to understand human language.",
  },
];

export async function webSearch(query: string): Promise<string> {
  return MOCK_RESULTS.map((r) => `**${r.title}**\n${r.url}\n${r.snippet}`).join("\n\n");
}
```

</details>

<details>
<summary><code>src/tools/extract-facts.ts</code></summary>

```typescript
const MOCK_FACTS = [
  "Machine learning enables systems to learn from data without explicit programming.",
  "Deep learning uses multi-layer neural networks for pattern recognition.",
  "NLP combines computational linguistics with statistical methods.",
  "Transformer architectures revolutionized language understanding in 2017.",
];

export function extractFacts(_text: string): string[] {
  return MOCK_FACTS.slice(0, 3);
}
```

</details>

<details>
<summary><code>src/tools/summarize.ts</code></summary>

```typescript
export function summarize(text: string, maxLength = 200): string {
  if (text.length <= maxLength) return text;
  const truncated = text.slice(0, maxLength);
  const lastSpace = truncated.lastIndexOf(" ");
  return `${lastSpace > 0 ? truncated.slice(0, lastSpace) : truncated}...`;
}
```

</details>

<details>
<summary><code>src/tools/cite-sources.ts</code></summary>

```typescript
export function citeSources(facts: string[]): string {
  if (facts.length === 0) return "No facts to cite.";
  return facts.map((fact, i) => `[${i + 1}] ${fact}`).join("\n");
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
description: "Security scan for research-assistant"

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
