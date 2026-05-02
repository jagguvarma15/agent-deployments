# Recipe: Parallel Enricher

**Status:** Blueprint (design spec)

**Composes:**

- Pattern: [Parallel Calls](../patterns/parallel-calls.md)
- Framework (Py): [Pydantic AI](../frameworks/pydantic-ai.md) (`asyncio.gather()` with multiple `agent.run()` calls)
- Framework (TS): [Vercel AI SDK](../frameworks/vercel-ai-sdk.md) (`Promise.all()` with `generateObject()` calls)
- Stack: [FastAPI](../stack/api-fastapi.md) / [Hono](../stack/api-hono.md), [Postgres](../stack/relational-postgres.md), [Redis](../stack/cache-redis.md), [Langfuse](../stack/tracing-langfuse.md)
- Cross-cutting: [Auth](../cross-cutting/auth-jwt.md), [Logging](../cross-cutting/logging-structured.md), [Observability](../cross-cutting/observability.md), [Rate limiting](../cross-cutting/rate-limiting.md)

## Load as Context

Feed these files to your AI coding assistant to build this agent:

**Core (always load):**
- `docs/recipes/parallel-enricher.md` — this blueprint
- `docs/patterns/parallel-calls.md` — the parallel calls pattern
- `docs/frameworks/pydantic-ai.md` (Python) or `docs/frameworks/vercel-ai-sdk.md` (TypeScript)
- `docs/stack/llm-claude.md` — LLM integration and model selection

**Stack (load for Tier 2 — API-ready):**
- `docs/stack/api-fastapi.md` or `docs/stack/api-hono.md` — API layer
- `docs/stack/cache-redis.md` — rate limiting backend

**Production concerns (load for Tier 3):**
- `docs/cross-cutting/auth-jwt.md` · `docs/cross-cutting/rate-limiting.md` · `docs/cross-cutting/logging-structured.md` · `docs/cross-cutting/observability.md` · `docs/cross-cutting/testing-strategy.md`

**Scaffolding:** `docs/reference/docker-templates.md` · `docs/reference/docker-compose-template.md`

> **Note:** This agent is stateless batch processing — Postgres is optional (only needed if you want to persist enrichment results).

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

## Data Models

### Python (Pydantic)

```python
from enum import Enum
from pydantic import BaseModel, Field


class CompanySize(str, Enum):
    startup = "startup"
    small = "small"
    mid_market = "mid-market"
    enterprise = "enterprise"
    unknown = "unknown"


class InputRecord(BaseModel):
    """A single record to enrich."""
    name: str = Field(..., min_length=1, description="Company or entity name")
    domain: str | None = Field(default=None, description="Website domain")
    email: str | None = Field(default=None, description="Contact email")
    extra: dict | None = Field(default=None, description="Any additional context")


class EnrichedRecord(BaseModel):
    """Enriched version of an input record."""
    name: str
    domain: str | None = None
    industry: str = Field(..., description="Inferred industry vertical")
    size: CompanySize = Field(..., description="Estimated company size")
    description: str = Field(..., description="One-line company description")
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance/quality score")
    tags: list[str] = Field(default_factory=list, description="Classification tags")
    enrichment_source: str = Field(default="llm", description="How enrichment was performed")


class EnrichmentError(BaseModel):
    """Tracks a failed enrichment."""
    name: str
    error: str


class EnrichBatchRequest(BaseModel):
    records: list[InputRecord] = Field(..., min_length=1, max_length=100)
    concurrency: int = Field(default=10, ge=1, le=50, description="Max parallel LLM calls")


class EnrichBatchResponse(BaseModel):
    enriched: list[EnrichedRecord]
    errors: list[EnrichmentError] = Field(default_factory=list)
    total: int
    succeeded: int
    failed: int
    trace_id: str
```

### TypeScript (Zod)

```typescript
import { z } from "zod";

export const CompanySize = z.enum(["startup", "small", "mid-market", "enterprise", "unknown"]);
export type CompanySize = z.infer<typeof CompanySize>;

export const InputRecord = z.object({
  name: z.string().min(1),
  domain: z.string().optional(),
  email: z.string().email().optional(),
  extra: z.record(z.unknown()).optional(),
});
export type InputRecord = z.infer<typeof InputRecord>;

export const EnrichedRecord = z.object({
  name: z.string(),
  domain: z.string().optional(),
  industry: z.string(),
  size: CompanySize,
  description: z.string(),
  score: z.number().min(0).max(1),
  tags: z.array(z.string()).default([]),
  enrichment_source: z.string().default("llm"),
});
export type EnrichedRecord = z.infer<typeof EnrichedRecord>;

export const EnrichmentError = z.object({
  name: z.string(),
  error: z.string(),
});

export const EnrichBatchRequest = z.object({
  records: z.array(InputRecord).min(1).max(100),
  concurrency: z.number().min(1).max(50).default(10),
});
export type EnrichBatchRequest = z.infer<typeof EnrichBatchRequest>;

export const EnrichBatchResponse = z.object({
  enriched: z.array(EnrichedRecord),
  errors: z.array(EnrichmentError).default([]),
  total: z.number(),
  succeeded: z.number(),
  failed: z.number(),
  trace_id: z.string(),
});
export type EnrichBatchResponse = z.infer<typeof EnrichBatchResponse>;
```

## API Contract

### `POST /enrich`

Enrich a batch of records in parallel.

**Request:**

```json
{
  "records": [
    {"name": "Acme Corp", "domain": "acme.com"},
    {"name": "Globex Inc", "domain": "globex.io"},
    {"name": "Initech", "email": "info@initech.com"}
  ],
  "concurrency": 10
}
```

**Response (200):**

```json
{
  "enriched": [
    {
      "name": "Acme Corp",
      "domain": "acme.com",
      "industry": "Manufacturing",
      "size": "mid-market",
      "description": "Industrial manufacturing company specializing in consumer products",
      "score": 0.72,
      "tags": ["b2b", "manufacturing", "consumer-goods"],
      "enrichment_source": "llm"
    },
    {
      "name": "Globex Inc",
      "domain": "globex.io",
      "industry": "Technology",
      "size": "startup",
      "description": "Developer tools startup focused on API infrastructure",
      "score": 0.85,
      "tags": ["b2b", "saas", "developer-tools"],
      "enrichment_source": "llm"
    }
  ],
  "errors": [
    {"name": "Initech", "error": "Enrichment timed out after 30s"}
  ],
  "total": 3,
  "succeeded": 2,
  "failed": 1,
  "trace_id": "c3d4e5f6-a7b8-9012-cdef-345678901234"
}
```

**Errors:**

| Status | Body | When |
|--------|------|------|
| 400 | `{"error": "Invalid request", "details": [...]}` | Empty records list or invalid concurrency |
| 413 | `{"error": "Batch too large", "max_records": 100}` | More than 100 records |
| 500 | `{"error": "Batch processing failed"}` | All records failed |

### `GET /health`

Returns `{"status": "ok"}`.

## Tool Specifications

This agent has **no external tools**. Each enrichment is a pure LLM call with structured output (`result_type=EnrichedRecord`). The agent uses the LLM's world knowledge to infer industry, size, and classification.

For production use, you would add tools for external data sources (Clearbit, LinkedIn, Crunchbase), but the core pattern — parallel fan-out with semaphore — remains the same.

## Prompt Specifications

### Enrichment prompt (per record)

```
You are a data enrichment specialist. Given a company or entity record,
enrich it with structured information.

Record to enrich:
{record_json}

For this record, determine:
1. Industry vertical (e.g., "Technology", "Healthcare", "Manufacturing")
2. Company size: startup (<50), small (50-200), mid-market (200-1000), enterprise (1000+), or unknown
3. A one-line description of what the company does
4. A relevance/quality score from 0.0 to 1.0 (how confident you are in the enrichment)
5. Classification tags (2-5 tags)

Base your assessment on the company name, domain, and any additional context provided.
If you're uncertain, set score lower and size to "unknown". Do not fabricate specific
revenue figures or employee counts.
```

**Design rationale:**
- **"Do not fabricate specific revenue figures"** — LLMs will confidently hallucinate numbers. The prompt constrains output to categorical assessments (size buckets, industry labels) where the model is more reliable.
- **Score as confidence signal** — Downstream consumers can filter enrichments below a threshold. Low-confidence enrichments are still useful but flagged.
- **Categorical size buckets** — More reliable than asking for exact employee counts. The model can reasonably distinguish "startup" from "enterprise" but not "487 employees" from "512 employees."

## Key files

### Python track

| File | Role |
|------|------|
| `app/main.py` | FastAPI entrypoint with lifespan, routers, health check |
| `app/settings.py` | Config: model name, default concurrency, batch size limit |
| `app/models/schemas.py` | All Pydantic models: `InputRecord`, `EnrichedRecord`, `EnrichBatchRequest/Response` |
| `app/agent/enricher.py` | Pydantic AI agent with `result_type=EnrichedRecord` |
| `app/agent/pipeline.py` | Fan-out orchestrator: split → semaphore → gather → aggregate |
| `app/api/enrich.py` | `/enrich` endpoint — accepts batch, returns enriched batch |

### TypeScript track

| File | Role |
|------|------|
| `src/index.ts` | Hono entrypoint with routes and health check |
| `src/config.ts` | Zod-validated env config |
| `src/schemas/index.ts` | All Zod schemas |
| `src/agent/enricher.ts` | `generateObject({ schema: EnrichedRecord })` per record |
| `src/agent/pipeline.ts` | Fan-out: `Promise.all()` with concurrency limiter |
| `src/api/enrich.ts` | `/enrich` route handler |

### Key implementation pattern (Python)

```python
import asyncio
from pydantic_ai import Agent

agent = Agent("anthropic:claude-sonnet-4-6-20250514", result_type=EnrichedRecord)

async def enrich_one(record: InputRecord, semaphore: asyncio.Semaphore) -> EnrichedRecord:
    async with semaphore:
        result = await agent.run(f"Enrich this record: {record.model_dump_json()}")
        return result.data

async def enrich_batch(records: list[InputRecord], concurrency: int = 10) -> list[EnrichedRecord | Exception]:
    semaphore = asyncio.Semaphore(concurrency)
    tasks = [enrich_one(r, semaphore) for r in records]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

### Key implementation pattern (TypeScript)

```typescript
import pLimit from "p-limit";
import { anthropic } from "@ai-sdk/anthropic";
import { generateObject } from "ai";

const limit = pLimit(10);

async function enrichBatch(records: InputRecord[]): Promise<(EnrichedRecord | Error)[]> {
  return Promise.all(
    records.map((record) =>
      limit(async () => {
        const result = await generateObject({
          model: anthropic(config.enrichModel),
          schema: EnrichedRecord,
          prompt: `Enrich this record: ${JSON.stringify(record)}`,
        });
        return result.object;
      })
    )
  );
}
```

## Implementation Roadmap

| Step | Task | Key deliverables |
|------|------|-----------------|
| 1 | **Project scaffolding** | FastAPI/Hono app with `/health`, settings, structured logging |
| 2 | **Data models** | All Pydantic + Zod schemas for input, enriched, batch request/response |
| 3 | **Enricher agent** | Pydantic AI agent with `result_type=EnrichedRecord`, system prompt |
| 4 | **Fan-out pipeline** | `asyncio.gather()` / `Promise.all()` with semaphore concurrency control |
| 5 | **Error handling** | `return_exceptions=True`, separate succeeded/failed in response |
| 6 | **API endpoint** | `POST /enrich` with batch size validation, trace ID |
| 7 | **Cross-cutting** | JWT auth, rate limiting, Langfuse tracing (one span per record) |
| 8 | **Unit tests** | Schema validation, semaphore behavior, error aggregation |
| 9 | **Integration + eval** | Batch enrichment with real LLM, promptfoo security scan |

## Environment & Deployment

### Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `ENRICH_MODEL` | No | `claude-sonnet-4-6-20250514` | Model for enrichment |
| `DEFAULT_CONCURRENCY` | No | `10` | Default parallel LLM calls |
| `MAX_BATCH_SIZE` | No | `100` | Maximum records per request |
| `DATABASE_URL` | No | `postgresql+asyncpg://agent:agent@localhost:5432/agent_db` | Postgres connection |
| `REDIS_URL` | No | `redis://localhost:6379` | Redis for rate limiting |
| `LANGFUSE_PUBLIC_KEY` | No | `pk-lf-local` | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | No | `sk-lf-local` | Langfuse secret key |
| `LANGFUSE_HOST` | No | `http://localhost:3000` | Langfuse server URL |
| `JWT_SECRET` | No | `change-me-in-production` | JWT signing secret |
| `APP_ENV` | No | `development` | Environment name |
| `LOG_LEVEL` | No | `INFO` | Log level |

### Docker Compose

See [Docker Compose template](../reference/docker-compose-template.md) for base infrastructure. This agent needs: Redis, Langfuse. Postgres is optional.

### Infrastructure dependencies

| Component | Required? | Why |
|-----------|-----------|-----|
| Postgres | Optional | Only if persisting enrichment results (batch processing is stateless) |
| Redis | Yes | Rate limiting backend |
| Qdrant | No | Not needed — this agent enriches records, not retrieves documents |
| Langfuse | Recommended | Per-record LLM call tracing (skip for local dev) |

## Test Strategy

### Unit tests

```python
def test_enriched_record_score_bounds():
    """Score must be between 0.0 and 1.0."""
    with pytest.raises(ValidationError):
        EnrichedRecord(name="x", industry="tech", size="startup",
                       description="d", score=1.5, tags=[])

def test_batch_request_max_size():
    """Batch requests are limited to 100 records."""
    records = [InputRecord(name=f"Company {i}") for i in range(101)]
    with pytest.raises(ValidationError):
        EnrichBatchRequest(records=records)

async def test_semaphore_limits_concurrency(mock_llm_client):
    """At most N enrichments run concurrently."""
    # Track max concurrent calls with a counter
    # Assert never exceeds semaphore limit

async def test_failed_records_dont_kill_batch(mock_llm_client):
    """One failing record doesn't prevent others from completing."""
    # Mock agent to fail on record 2 of 5
    # Assert 4 succeeded, 1 in errors list
```

### Integration tests (main branch only)

```python
async def test_batch_enrichment_e2e():
    """Enrich 3 records with real LLM, all should succeed."""
    response = await client.post("/enrich", json={
        "records": [
            {"name": "Stripe", "domain": "stripe.com"},
            {"name": "Anthropic", "domain": "anthropic.com"},
            {"name": "Vercel", "domain": "vercel.com"},
        ]
    })
    assert response.status_code == 200
    data = response.json()
    assert data["succeeded"] == 3
    assert data["failed"] == 0
    assert all(r["industry"] for r in data["enriched"])
```

### Eval assertions

- Well-known companies (Stripe, Google) get score ≥ 0.8
- Unknown/ambiguous names get score < 0.5 and size "unknown"
- Industry classification is reasonable (Stripe → "Technology" or "Fintech")
- Batch of 10 completes within 30s at concurrency=10

## Eval Dataset

```jsonl
{"input": {"records": [{"name": "Stripe", "domain": "stripe.com"}]}, "expected_industry": "Technology", "expected_min_score": 0.8}
{"input": {"records": [{"name": "Mayo Clinic", "domain": "mayoclinic.org"}]}, "expected_industry": "Healthcare", "expected_min_score": 0.7}
{"input": {"records": [{"name": "XYZZY Corp"}]}, "expected_size": "unknown", "expected_max_score": 0.5}
{"input": {"records": [{"name": "Toyota", "domain": "toyota.com"}]}, "expected_industry": "Automotive", "expected_min_score": 0.8}
{"input": {"records": [{"name": "Anthropic", "domain": "anthropic.com"}]}, "expected_industry": "Technology", "expected_min_score": 0.8}
{"input": {"records": [{"name": "a"}, {"name": "b"}, {"name": "c"}]}, "expected_total": 3}
```

## Design decisions

- **Semaphore-based concurrency:** `asyncio.Semaphore(10)` limits parallel LLM calls to 10. Prevents rate-limit exhaustion while maximizing throughput.
- **`return_exceptions=True`:** Individual record failures don't kill the batch. Failed records are reported separately in the `errors` list.
- **Structured output per record:** `result_type=EnrichedRecord` ensures every enrichment returns validated structured data, not free text.
- **Pydantic AI for simplicity:** No graph or workflow needed. Raw `asyncio.gather()` with Pydantic AI agents is the cleanest pattern for parallel independent work.
- **Configurable concurrency:** The caller controls parallelism per request. High-priority small batches can use higher concurrency; large batches can throttle down.
