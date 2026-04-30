# Recipe: Content Pipeline

**Status:** Skeleton (design intent)

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

## Intended key files

### Python track

| File | Role |
|------|------|
| `app/agent/pipeline.py` | Pipeline orchestrator — runs stages sequentially, validates between stages |
| `app/agent/stages/research.py` | Stage 1: Research agent with `result_type=ResearchNotes` |
| `app/agent/stages/outline.py` | Stage 2: Outline agent with `result_type=ContentOutline` |
| `app/agent/stages/draft.py` | Stage 3: Draft agent with `result_type=ContentDraft` |
| `app/agent/stages/edit.py` | Stage 4: Edit agent with `result_type=FinalContent` |
| `app/models/schemas.py` | Stage schemas: `ResearchNotes`, `ContentOutline`, `ContentDraft`, `FinalContent` |
| `app/api/pipeline.py` | `/pipeline` endpoint — accepts topic, returns final content + intermediate stages |

## Example interaction

```bash
curl -X POST http://localhost:8000/pipeline \
  -H "Content-Type: application/json" \
  -d '{"topic": "AI agent design patterns", "content_type": "blog_post"}'
```

Expected response:

```json
{
  "final_content": {
    "title": "A Practical Guide to AI Agent Design Patterns",
    "body": "...",
    "summary": "...",
    "word_count": 1200
  },
  "stages_completed": 4,
  "trace_id": "..."
}
```

## Design intent

- **Typed schemas between stages:** Each stage produces a Pydantic model (Py) or Zod schema (TS). The pipeline validates output before passing it forward. This catches bad outputs early instead of letting them cascade.
- **Independent stage prompts:** Each stage has a focused system prompt. The research stage is told to be thorough; the edit stage is told to be concise. Specialization per stage beats one monolithic prompt.
- **Persist intermediate outputs:** Each stage's output is saved to Postgres. If stage 3 fails, you don't re-run stages 1-2.
- **Configurable stage models:** Research and outline stages can use a cheaper model; draft and edit stages benefit from a more capable model.
