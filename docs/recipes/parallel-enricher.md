# Recipe: Parallel Enricher

**Status:** Skeleton (design intent)

**Composes:**

- Pattern: [Parallel Calls](../patterns/parallel-calls.md)
- Framework (Py): [Pydantic AI](../frameworks/pydantic-ai.md) (`asyncio.gather()` with multiple `agent.run()` calls)
- Framework (TS): [Vercel AI SDK](../frameworks/vercel-ai-sdk.md) (`Promise.all()` with `generateObject()` calls)
- Stack: [FastAPI](../stack/api-fastapi.md) / [Hono](../stack/api-hono.md), [Postgres](../stack/relational-postgres.md), [Redis](../stack/cache-redis.md), [Langfuse](../stack/tracing-langfuse.md)
- Cross-cutting: [Auth](../cross-cutting/auth-jwt.md), [Logging](../cross-cutting/logging-structured.md), [Observability](../cross-cutting/observability.md), [Rate limiting](../cross-cutting/rate-limiting.md)

## What it does

A batch enrichment agent. Given a list of records (e.g., company names, contact emails, product URLs), the agent enriches each record in parallel — extracting structured data, classifying, scoring, and augmenting with external information. Results are aggregated into a structured output.

This implements **homogeneous fan-out with concurrency control** — the same enrichment prompt runs on each item concurrently, with a semaphore limiting parallel LLM calls to avoid rate limits.

## Architecture

```
Input (list of N records)
    |
    v
[Splitter] ──> N individual records
    |
    v
[Concurrency controller: semaphore(10)]
    |
    ├──> [Enrich record 1] ──┐
    ├──> [Enrich record 2] ──┤
    ├──> [Enrich record 3] ──┤
    │    ...                  │
    └──> [Enrich record N] ──┘
                              |
                              v
                     [Aggregator]
                              |
                              v
                     Enriched dataset
```

## Intended key files

### Python track

| File | Role |
|------|------|
| `app/agent/enricher.py` | Pydantic AI agent with `result_type=EnrichedRecord` |
| `app/agent/pipeline.py` | Fan-out orchestrator: split → gather → aggregate |
| `app/models/schemas.py` | `InputRecord`, `EnrichedRecord`, `EnrichmentBatch` schemas |
| `app/api/enrich.py` | `/enrich` endpoint — accepts batch, returns enriched batch |

### Key implementation pattern (Python)

```python
import asyncio
from pydantic_ai import Agent

agent = Agent("anthropic:claude-sonnet-4-6-20250514", result_type=EnrichedRecord)
semaphore = asyncio.Semaphore(10)

async def enrich_one(record: InputRecord) -> EnrichedRecord:
    async with semaphore:
        result = await agent.run(f"Enrich this record: {record.model_dump_json()}")
        return result.data

async def enrich_batch(records: list[InputRecord]) -> list[EnrichedRecord]:
    tasks = [enrich_one(r) for r in records]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

## Example interaction

```bash
curl -X POST http://localhost:8000/enrich \
  -H "Content-Type: application/json" \
  -d '{
    "records": [
      {"name": "Acme Corp", "domain": "acme.com"},
      {"name": "Globex Inc", "domain": "globex.io"}
    ]
  }'
```

Expected response:

```json
{
  "enriched": [
    {
      "name": "Acme Corp",
      "domain": "acme.com",
      "industry": "Manufacturing",
      "size": "mid-market",
      "score": 0.72
    },
    {
      "name": "Globex Inc",
      "domain": "globex.io",
      "industry": "Technology",
      "size": "startup",
      "score": 0.85
    }
  ],
  "total": 2,
  "succeeded": 2,
  "failed": 0,
  "trace_id": "..."
}
```

## Design intent

- **Semaphore-based concurrency:** `asyncio.Semaphore(10)` limits parallel LLM calls to 10. Prevents rate-limit exhaustion while maximizing throughput.
- **`return_exceptions=True`:** Individual record failures don't kill the batch. Failed records are reported separately.
- **Structured output per record:** `result_type=EnrichedRecord` ensures every enrichment returns validated structured data, not free text.
- **Pydantic AI for simplicity:** No graph or workflow needed. Raw `asyncio.gather()` with Pydantic AI agents is the cleanest pattern for parallel independent work.
