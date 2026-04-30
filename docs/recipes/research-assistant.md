# Recipe: Research Assistant

**Status:** Fully implemented (both tracks)

**Composes:**

- Pattern: [ReAct](../patterns/react.md)
- Framework (Py): [Pydantic AI](../frameworks/pydantic-ai.md) (agent with tool-based ReAct loop)
- Framework (TS): [Vercel AI SDK](../frameworks/vercel-ai-sdk.md) (`generateText` with tools + `maxSteps`)
- Stack: [FastAPI](../stack/api-fastapi.md) / [Hono](../stack/api-hono.md), [Postgres](../stack/relational-postgres.md), [Redis](../stack/cache-redis.md), [Langfuse](../stack/tracing-langfuse.md)
- Cross-cutting: [Auth](../cross-cutting/auth-jwt.md), [Logging](../cross-cutting/logging-structured.md), [Observability](../cross-cutting/observability.md), [Rate limiting](../cross-cutting/rate-limiting.md)

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

## Run locally

```bash
cd prototypes/research-assistant/python   # or typescript
cp .env.example .env
# Add ANTHROPIC_API_KEY to .env
docker compose up
```

Or from repo root:

```bash
make up PROTOTYPE=research-assistant TRACK=python
```

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

## Eval setup

- **Dataset:** `eval/dataset.jsonl` — research questions with expected answer characteristics
- **Unit tests:** `tests/unit/` — test schema validation, API routes, tool mocks
- **Integration tests:** `tests/integration/` — test full research pipeline with real LLM
- **Eval metrics:** Answer completeness, source quality, reasoning coherence
- **Security scan:** `eval/promptfoo.yaml` — jailbreak and prompt injection tests

```bash
make test PROTOTYPE=research-assistant TRACK=python
make eval PROTOTYPE=research-assistant TRACK=python
```

## Design decisions

- **Pydantic AI over LangGraph (Python):** The built-in ReAct loop in `agent.run()` is sufficient for a single-agent research flow. LangGraph's `create_react_agent()` would add state management value only if we needed checkpointing for long-running research sessions.
- **Multiple specialized tools over one generic tool:** Having separate `web_search`, `extract_facts`, `summarize`, and `cite_sources` tools guides the agent toward a structured research process. A single `search_and_answer` tool would produce lower-quality research.
- **Step limit at 5:** Balances thoroughness vs. cost. Most research questions resolve in 2-3 tool calls. The limit prevents runaway loops on unanswerable questions.
