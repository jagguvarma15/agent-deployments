# Recipe: Customer Support Triage

**Status:** Fully implemented (both tracks)

**Composes:**

- Pattern: [Routing + Tool Use](../patterns/routing-tool-use.md)
- Framework (Py): [Pydantic AI](../frameworks/pydantic-ai.md) (structured classification + specialist agents)
- Framework (TS): [Vercel AI SDK](../frameworks/vercel-ai-sdk.md) (`generateObject` for classification, `generateText` for specialists)
- Stack: [FastAPI](../stack/api-fastapi.md) / [Hono](../stack/api-hono.md), [Postgres](../stack/relational-postgres.md), [Redis](../stack/cache-redis.md), [Langfuse](../stack/tracing-langfuse.md)
- Cross-cutting: [Auth](../cross-cutting/auth-jwt.md), [Logging](../cross-cutting/logging-structured.md), [Observability](../cross-cutting/observability.md), [Rate limiting](../cross-cutting/rate-limiting.md)

## What it does

A customer support triage agent. Users send a message, the agent classifies the intent (billing, technical, account, or general), then routes to a specialized agent with the right tools for that intent. The billing specialist can look up Stripe data; the technical and account specialists can search a knowledge base.

This implements **single-hop routing** — classify once, route once. The classifier returns structured output (intent enum + confidence + reasoning), and a simple match/switch dispatches to the correct specialist.

## Architecture

```
                    ┌─────────────┐
                    │   Client    │
                    └──────┬──────┘
                           │
                      POST /triage
                           │
                    ┌──────▼──────┐
                    │   FastAPI   │ (or Hono)
                    │   + Auth    │
                    │   + Rate    │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Classifier │ (cheap model)
                    │  → intent   │
                    │  + confidence│
                    └──────┬──────┘
                           │
          ┌────────┬───────┼───────┬────────┐
          v        v       v       v        │
     [Billing] [Technical] [Account] [General]
     (Stripe   (KB search) (KB search) (no tools)
      lookup)
          │        │       │       │
          └────────┴───────┴───────┘
                           │
                    ┌──────▼──────┐
                    │  Response   │
                    └─────────────┘
```

### Triage flow

1. Client POSTs a message to `/triage`.
2. Classifier agent produces structured output: `{intent, confidence, reasoning}`.
3. Router dispatches to the specialist agent for that intent.
4. Specialist processes the message using its tools (Stripe lookup, KB search, or none).
5. Response includes the specialist's answer, the classification, and tool calls made.

## Key files

### Python track

| File | Role |
|------|------|
| `app/main.py` | FastAPI app with lifespan (DB init, logging config) |
| `app/settings.py` | Pydantic-settings config (classifier model, specialist model) |
| `app/agent/classifier.py` | Pydantic AI agent with `result_type=ClassificationResult` |
| `app/agent/specialists.py` | Factory for specialist agents — one per intent, each with its own tools |
| `app/api/triage.py` | `/triage` endpoint — classify, route, respond |
| `app/tools/stripe.py` | Stripe billing lookup tool |
| `app/tools/kb.py` | Knowledge base search tool |
| `app/models/schemas.py` | Pydantic schemas: `ClassificationResult`, `Intent` enum, request/response |
| `app/db/models.py` | SQLAlchemy models for conversation logging |

### TypeScript track

| File | Role |
|------|------|
| `src/index.ts` | Hono app entry point |
| `src/config.ts` | Zod-validated config from env |
| `src/agent/classifier.ts` | Vercel AI SDK `generateObject()` for intent classification |
| `src/agent/specialists.ts` | Specialist agents per intent with `generateText()` + tools |
| `src/api/triage.ts` | `/triage` route handler |
| `src/tools/stripe.ts` | Stripe billing lookup tool |
| `src/tools/kb.ts` | Knowledge base search tool |
| `src/schemas/index.ts` | Zod schemas for classification and request/response |

## Run locally

```bash
cd prototypes/customer-support-triage/python   # or typescript
cp .env.example .env
# Add ANTHROPIC_API_KEY to .env
docker compose up
```

Or from repo root:

```bash
make up PROTOTYPE=customer-support-triage TRACK=python
```

## Example interaction

```bash
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{"message": "I was charged twice for my subscription last month"}'
```

Response:

```json
{
  "classification": {
    "intent": "billing",
    "confidence": 0.95,
    "reasoning": "Customer is reporting a duplicate charge on their subscription"
  },
  "response": "I understand you're concerned about a duplicate charge. Let me look into your billing history...",
  "specialist": "billing",
  "tool_calls": [
    {"tool_name": "lookup_billing", "args": {"query": "duplicate charge subscription"}}
  ]
}
```

## Eval setup

- **Dataset:** `eval/dataset.jsonl` — customer messages with expected intent labels
- **Unit tests:** `tests/unit/` — test classifier output schema, specialist routing, tool mocks
- **Integration tests:** `tests/integration/` — test full triage pipeline with real LLM
- **Eval metrics:** Classification accuracy, routing correctness, response relevance
- **Security scan:** `eval/promptfoo.yaml` — jailbreak and prompt injection tests

```bash
make test PROTOTYPE=customer-support-triage TRACK=python
make eval PROTOTYPE=customer-support-triage TRACK=python
```

## Design decisions

- **Separate classifier and specialist models:** The classifier can use a cheaper/faster model since it only needs to produce structured classification. Specialists use the full model for nuanced responses.
- **Pydantic AI `result_type` for classification:** Structured output validation ensures the classifier always returns a valid intent enum, not a free-text guess.
- **Isolated specialist agents:** Each specialist has only its own tools. The billing agent can't accidentally search the KB, and the technical agent can't call Stripe. This prevents tool misuse.
- **Confidence score:** The classifier returns a confidence score, enabling future gating (e.g., fall back to general handler below 0.7 confidence).
