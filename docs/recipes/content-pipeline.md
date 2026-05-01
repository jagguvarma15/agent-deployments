# Recipe: Content Pipeline

**Status:** Blueprint (design spec)

**Composes:**

- Pattern: [Prompt Chaining](../patterns/prompt-chaining.md)
- Framework (Py): [Pydantic AI](../frameworks/pydantic-ai.md) (sequential `agent.run()` with typed `result_type` per stage)
- Framework (TS): [Vercel AI SDK](../frameworks/vercel-ai-sdk.md) (sequential `generateObject()` / `generateText()` calls)
- Stack: [FastAPI](../stack/api-fastapi.md) / [Hono](../stack/api-hono.md), [Postgres](../stack/relational-postgres.md), [Redis](../stack/cache-redis.md), [Langfuse](../stack/tracing-langfuse.md)
- Cross-cutting: [Auth](../cross-cutting/auth-jwt.md), [Logging](../cross-cutting/logging-structured.md), [Observability](../cross-cutting/observability.md), [Rate limiting](../cross-cutting/rate-limiting.md)

## What it does

A multi-stage content generation pipeline. Given a topic and content type (blog post, newsletter, technical doc), the agent runs a fixed sequence of stages: research → outline → draft → edit → publish-ready output. Each stage has a specialized prompt and produces structured output that feeds the next stage.

This implements **linear prompt chaining with validation gates** — each stage's output is validated against a Pydantic/Zod schema before passing to the next stage.

## Architecture

```
Input (topic + content type)
    |
    v
[Stage 1: Research]     ──> ResearchNotes { facts, sources, key_points }
    |
    v
[Stage 2: Outline]      ──> ContentOutline { title, sections[], key_messages }
    |
    v
[Stage 3: Draft]        ──> ContentDraft { body, word_count, tone }
    |
    v
[Stage 4: Edit]         ──> FinalContent { body, summary, metadata }
    |
    v
Publish-ready output
```

## Data Models

### Python (Pydantic)

```python
from enum import Enum
from pydantic import BaseModel, Field


class ContentType(str, Enum):
    blog_post = "blog_post"
    newsletter = "newsletter"
    technical_doc = "technical_doc"


class PipelineRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="Topic to generate content about")
    content_type: ContentType = Field(..., description="Type of content to produce")
    target_word_count: int = Field(default=1200, ge=200, le=5000, description="Approximate word count for the draft")


class Source(BaseModel):
    title: str
    url: str | None = None
    relevance: str = Field(..., description="Why this source is relevant to the topic")


class ResearchNotes(BaseModel):
    """Stage 1 output: raw research material."""
    facts: list[str] = Field(..., min_length=3, description="Key facts discovered")
    sources: list[Source] = Field(default_factory=list, description="Sources referenced")
    key_points: list[str] = Field(..., min_length=2, description="Main points to cover")
    target_audience: str = Field(..., description="Inferred target audience")


class Section(BaseModel):
    heading: str
    bullet_points: list[str] = Field(..., min_length=1)


class ContentOutline(BaseModel):
    """Stage 2 output: structured outline."""
    title: str = Field(..., description="Proposed title")
    sections: list[Section] = Field(..., min_length=2, description="Ordered sections")
    key_messages: list[str] = Field(..., min_length=1, description="Core messages the piece should convey")
    estimated_word_count: int


class ContentDraft(BaseModel):
    """Stage 3 output: full draft."""
    body: str = Field(..., min_length=100, description="Full draft in markdown")
    word_count: int
    tone: str = Field(..., description="Detected tone: formal, conversational, technical")


class ContentMetadata(BaseModel):
    seo_title: str = Field(..., max_length=60)
    meta_description: str = Field(..., max_length=160)
    tags: list[str]


class FinalContent(BaseModel):
    """Stage 4 output: polished, publish-ready content."""
    title: str
    body: str
    summary: str = Field(..., max_length=300, description="Executive summary")
    word_count: int
    metadata: ContentMetadata


class PipelineResponse(BaseModel):
    final_content: FinalContent
    stages_completed: int
    trace_id: str
```

### TypeScript (Zod)

```typescript
import { z } from "zod";

export const ContentType = z.enum(["blog_post", "newsletter", "technical_doc"]);
export type ContentType = z.infer<typeof ContentType>;

export const PipelineRequest = z.object({
  topic: z.string().min(1),
  content_type: ContentType,
  target_word_count: z.number().min(200).max(5000).default(1200),
});
export type PipelineRequest = z.infer<typeof PipelineRequest>;

export const Source = z.object({
  title: z.string(),
  url: z.string().url().optional(),
  relevance: z.string(),
});

export const ResearchNotes = z.object({
  facts: z.array(z.string()).min(3),
  sources: z.array(Source).default([]),
  key_points: z.array(z.string()).min(2),
  target_audience: z.string(),
});
export type ResearchNotes = z.infer<typeof ResearchNotes>;

export const Section = z.object({
  heading: z.string(),
  bullet_points: z.array(z.string()).min(1),
});

export const ContentOutline = z.object({
  title: z.string(),
  sections: z.array(Section).min(2),
  key_messages: z.array(z.string()).min(1),
  estimated_word_count: z.number(),
});
export type ContentOutline = z.infer<typeof ContentOutline>;

export const ContentDraft = z.object({
  body: z.string().min(100),
  word_count: z.number(),
  tone: z.string(),
});
export type ContentDraft = z.infer<typeof ContentDraft>;

export const ContentMetadata = z.object({
  seo_title: z.string().max(60),
  meta_description: z.string().max(160),
  tags: z.array(z.string()),
});

export const FinalContent = z.object({
  title: z.string(),
  body: z.string(),
  summary: z.string().max(300),
  word_count: z.number(),
  metadata: ContentMetadata,
});
export type FinalContent = z.infer<typeof FinalContent>;

export const PipelineResponse = z.object({
  final_content: FinalContent,
  stages_completed: z.number(),
  trace_id: z.string(),
});
export type PipelineResponse = z.infer<typeof PipelineResponse>;
```

### Database models (SQLAlchemy)

```python
class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    topic = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    current_stage = Column(Integer, default=0)
    status = Column(String, default="pending")  # pending, running, completed, failed
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    stages = relationship("StageResult", back_populates="run", order_by="StageResult.stage_number")


class StageResult(Base):
    __tablename__ = "stage_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("pipeline_runs.id"), nullable=False, index=True)
    stage_number = Column(Integer, nullable=False)
    stage_name = Column(String, nullable=False)
    output_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    run = relationship("PipelineRun", back_populates="stages")
```

## API Contract

### `POST /pipeline`

Start a content generation pipeline.

**Request:**

```json
{
  "topic": "AI agent design patterns",
  "content_type": "blog_post",
  "target_word_count": 1200
}
```

**Response (200):**

```json
{
  "final_content": {
    "title": "A Practical Guide to AI Agent Design Patterns",
    "body": "## Introduction\n\nAI agents are transforming...",
    "summary": "An overview of nine production-ready agent patterns...",
    "word_count": 1247,
    "metadata": {
      "seo_title": "AI Agent Design Patterns Guide 2026",
      "meta_description": "Learn nine production-ready AI agent patterns with examples...",
      "tags": ["ai-agents", "design-patterns", "llm"]
    }
  },
  "stages_completed": 4,
  "trace_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
}
```

**Errors:**

| Status | Body | When |
|--------|------|------|
| 400 | `{"error": "Invalid request", "details": [...]}` | Validation failure |
| 422 | `{"error": "Stage N validation failed", "stage": N, "details": "..."}` | Stage output doesn't match schema |
| 500 | `{"error": "Pipeline failed", "stages_completed": N}` | LLM or internal error |

### `GET /health`

Returns `{"status": "ok"}`.

## Tool Specifications

This agent has **no external tools**. Each stage is a pure LLM call with structured output (`result_type` / `generateObject`). The pipeline's power comes from chaining, not tool use.

The orchestrator itself acts as the "tool" — it validates each stage's output and passes it to the next stage as context.

## Prompt Specifications

### Stage 1: Research

```
You are a research specialist. Given a topic and content type, gather comprehensive
research material.

Topic: {topic}
Content type: {content_type}
Target audience: infer from the topic and content type

Research thoroughly:
1. Identify at least 5 key facts about the topic
2. Note credible sources where possible
3. Identify the main points that should be covered
4. Consider the target audience's existing knowledge level

Be factual and specific. Avoid vague generalities.
```

**Design rationale:** The research stage is told to be thorough and factual. It explicitly requests structured output (facts, sources, key points) to constrain free-form exploration.

### Stage 2: Outline

```
You are a content strategist. Given research notes, create a structured outline
for a {content_type}.

Research notes:
{research_notes_json}

Target word count: {target_word_count}

Create an outline with:
1. A compelling title
2. Logical section structure (3-6 sections)
3. Bullet points for each section's key content
4. Core messages the piece should convey

The outline should flow naturally from introduction to conclusion.
```

**Design rationale:** Receives the full research output as JSON. The explicit section count range (3-6) prevents both skeletal and bloated outlines.

### Stage 3: Draft

```
You are a skilled content writer. Given an outline, write a complete {content_type}.

Outline:
{outline_json}

Research notes (for accuracy):
{research_notes_json}

Requirements:
- Target word count: {target_word_count}
- Tone: match the content type ({content_type})
- Use markdown formatting
- Include all sections from the outline
- Be specific and substantive — no filler

Write the complete draft now.
```

**Design rationale:** Both the outline AND original research are provided. The outline gives structure; the research prevents the writer from drifting from facts. Explicit anti-filler instruction.

### Stage 4: Edit

```
You are a senior editor. Review and polish this draft for publication.

Draft:
{draft_body}

Original outline:
{outline_json}

Edit for:
1. Clarity and conciseness — remove filler, tighten prose
2. Accuracy — flag any claims not supported by the research
3. Flow — ensure smooth transitions between sections
4. Tone consistency — maintain {content_type} conventions
5. SEO — create a title (≤60 chars), meta description (≤160 chars), and tags

Return the final, publish-ready version.
```

**Design rationale:** The editor sees both the draft and the outline to verify completeness. The SEO metadata requirement is placed at the edit stage because it needs the final content to be effective.

## Key files

### Python track

| File | Role |
|------|------|
| `app/main.py` | FastAPI entrypoint with lifespan, routers, health check |
| `app/settings.py` | `pydantic-settings` config: models per stage, word count defaults |
| `app/models/schemas.py` | All Pydantic models: `PipelineRequest`, stage outputs, `PipelineResponse` |
| `app/agent/pipeline.py` | Pipeline orchestrator — runs stages sequentially, validates between stages |
| `app/agent/stages/research.py` | Stage 1: Research agent with `result_type=ResearchNotes` |
| `app/agent/stages/outline.py` | Stage 2: Outline agent with `result_type=ContentOutline` |
| `app/agent/stages/draft.py` | Stage 3: Draft agent with `result_type=ContentDraft` |
| `app/agent/stages/edit.py` | Stage 4: Edit agent with `result_type=FinalContent` |
| `app/api/pipeline.py` | `/pipeline` endpoint — accepts topic, returns final content + intermediate stages |
| `app/db/models.py` | SQLAlchemy models: `PipelineRun`, `StageResult` |
| `app/db/session.py` | Async session factory |

### TypeScript track

| File | Role |
|------|------|
| `src/index.ts` | Hono entrypoint with routes and health check |
| `src/config.ts` | Zod-validated env config |
| `src/schemas/index.ts` | All Zod schemas |
| `src/agent/pipeline.ts` | Pipeline orchestrator — sequential `generateObject()` calls |
| `src/agent/stages/research.ts` | Stage 1: `generateObject({ schema: ResearchNotes })` |
| `src/agent/stages/outline.ts` | Stage 2: `generateObject({ schema: ContentOutline })` |
| `src/agent/stages/draft.ts` | Stage 3: `generateObject({ schema: ContentDraft })` |
| `src/agent/stages/edit.ts` | Stage 4: `generateObject({ schema: FinalContent })` |
| `src/api/pipeline.ts` | `/pipeline` route handler |

## Implementation Roadmap

| Step | Task | Key deliverables |
|------|------|-----------------|
| 1 | **Project scaffolding** | FastAPI/Hono app with `/health`, settings, structured logging |
| 2 | **Data models** | All Pydantic + Zod schemas for request, 4 stage outputs, response |
| 3 | **Database models** | `PipelineRun` and `StageResult` tables, async session factory |
| 4 | **Stage 1: Research** | Pydantic AI agent with `result_type=ResearchNotes`, system prompt |
| 5 | **Stage 2: Outline** | Agent takes research JSON, produces `ContentOutline` |
| 6 | **Stage 3: Draft** | Agent takes outline + research, produces `ContentDraft` |
| 7 | **Stage 4: Edit** | Agent takes draft + outline, produces `FinalContent` with metadata |
| 8 | **Pipeline orchestrator** | Sequential runner with validation gates, stage persistence to DB |
| 9 | **API endpoint** | `POST /pipeline` wired to orchestrator, trace ID generation |
| 10 | **Cross-cutting** | JWT auth, rate limiting, Langfuse tracing on each stage |
| 11 | **Unit tests** | Schema validation, pipeline with mocked agents, stage isolation |
| 12 | **Integration + eval** | End-to-end pipeline run, promptfoo security scan |

## Environment & Deployment

### Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `RESEARCH_MODEL` | No | `claude-haiku-4-5-20251001` | Model for research stage (cheaper) |
| `OUTLINE_MODEL` | No | `claude-haiku-4-5-20251001` | Model for outline stage (cheaper) |
| `DRAFT_MODEL` | No | `claude-sonnet-4-6-20250514` | Model for draft stage (more capable) |
| `EDIT_MODEL` | No | `claude-sonnet-4-6-20250514` | Model for edit stage (more capable) |
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

## Test Strategy

### Unit tests

```python
def test_research_notes_validation():
    """Stage output must have at least 3 facts and 2 key points."""
    with pytest.raises(ValidationError):
        ResearchNotes(facts=["one"], sources=[], key_points=[], target_audience="devs")

def test_pipeline_persists_stages(mock_llm_client):
    """Each stage result is saved to DB before proceeding to next."""
    # Run pipeline with mocked agents
    # Assert 4 StageResult rows created
    # Assert PipelineRun.status == "completed"

def test_pipeline_stops_on_validation_failure(mock_llm_client):
    """If stage output fails schema validation, pipeline halts with 422."""
    # Mock stage 2 to return invalid outline (0 sections)
    # Assert pipeline stops, returns stages_completed=1
```

### Integration tests (main branch only)

```python
async def test_full_pipeline_e2e():
    """Run complete pipeline with real LLM — verify 4 stages complete."""
    response = await client.post("/pipeline", json={
        "topic": "benefits of structured logging",
        "content_type": "blog_post",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["stages_completed"] == 4
    assert len(data["final_content"]["body"]) > 200
```

### Eval assertions

- Final content word count is within ±30% of `target_word_count`
- All outline sections appear in the final draft
- SEO title is ≤60 characters, meta description ≤160 characters
- No "lorem ipsum" or placeholder text in the final output

## Eval Dataset

```jsonl
{"input": {"topic": "AI agent design patterns", "content_type": "blog_post"}, "expected_stages": 4, "min_word_count": 800}
{"input": {"topic": "structured logging best practices", "content_type": "technical_doc"}, "expected_stages": 4, "min_word_count": 1000}
{"input": {"topic": "weekly engineering highlights", "content_type": "newsletter"}, "expected_stages": 4, "min_word_count": 400}
{"input": {"topic": "microservices vs monolith tradeoffs", "content_type": "blog_post"}, "expected_stages": 4, "min_word_count": 800}
{"input": {"topic": "Kubernetes cost optimization", "content_type": "technical_doc"}, "expected_stages": 4, "min_word_count": 1000}
{"input": {"topic": "new hire onboarding process", "content_type": "newsletter"}, "expected_stages": 4, "min_word_count": 400}
```

## Design decisions

- **Typed schemas between stages:** Each stage produces a Pydantic model (Py) or Zod schema (TS). The pipeline validates output before passing it forward. This catches bad outputs early instead of letting them cascade.
- **Independent stage prompts:** Each stage has a focused system prompt. The research stage is told to be thorough; the edit stage is told to be concise. Specialization per stage beats one monolithic prompt.
- **Persist intermediate outputs:** Each stage's output is saved to Postgres. If stage 3 fails, you don't re-run stages 1-2.
- **Configurable stage models:** Research and outline stages can use a cheaper model; draft and edit stages benefit from a more capable model.
- **No tools, pure chaining:** This agent deliberately avoids tool use. The pattern it demonstrates is sequential LLM calls with structured output — the simplest possible multi-step agent.
