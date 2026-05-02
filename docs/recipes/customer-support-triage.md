# Recipe: Customer Support Triage

**Status:** Blueprint (validated)

**Composes:**

- Pattern: [Routing + Tool Use](../patterns/routing-tool-use.md)
- Framework (Py): [Pydantic AI](../frameworks/pydantic-ai.md) (structured classification + specialist agents)
- Framework (TS): [Vercel AI SDK](../frameworks/vercel-ai-sdk.md) (`generateObject` for classification, `generateText` for specialists)
- Stack: [FastAPI](../stack/api-fastapi.md) / [Hono](../stack/api-hono.md), [Postgres](../stack/relational-postgres.md), [Redis](../stack/cache-redis.md), [Langfuse](../stack/tracing-langfuse.md)
- Cross-cutting: [Auth](../cross-cutting/auth-jwt.md), [Logging](../cross-cutting/logging-structured.md), [Observability](../cross-cutting/observability.md), [Rate limiting](../cross-cutting/rate-limiting.md)

## Load as Context

Feed these files to your AI coding assistant to build this agent:

**Core (always load):**
- `docs/recipes/customer-support-triage.md` — this blueprint
- `docs/patterns/routing-tool-use.md` — the routing + tool use pattern
- `docs/frameworks/pydantic-ai.md` (Python) or `docs/frameworks/vercel-ai-sdk.md` (TypeScript)
- `docs/stack/llm-claude.md` — LLM integration and model selection

**Stack (load for Tier 2 — API-ready):**
- `docs/stack/api-fastapi.md` or `docs/stack/api-hono.md` — API layer
- `docs/stack/relational-postgres.md` — conversation logging
- `docs/stack/cache-redis.md` — rate limiting backend
- `docs/stack/vector-qdrant.md` — knowledge base search (if using vector retrieval)

**Production concerns (load for Tier 3):**
- `docs/cross-cutting/auth-jwt.md` · `docs/cross-cutting/rate-limiting.md` · `docs/cross-cutting/logging-structured.md` · `docs/cross-cutting/observability.md` · `docs/cross-cutting/testing-strategy.md`

**Scaffolding:** `docs/reference/docker-templates.md` · `docs/reference/docker-compose-template.md`

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

## Data Models

### Python (Pydantic)

```python
from enum import Enum
from pydantic import BaseModel, Field


class Intent(str, Enum):
    billing = "billing"
    technical = "technical"
    account = "account"
    general = "general"


class ClassificationResult(BaseModel):
    intent: Intent
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str


class TriageRequest(BaseModel):
    message: str = Field(..., min_length=1)
    user_id: str = Field(default="anonymous")


class TriageResponse(BaseModel):
    conversation_id: str
    intent: str
    specialist_response: str
    escalated: bool
    trace_id: str
```

### TypeScript (Zod)

```typescript
import { z } from "zod";

export const Intent = z.enum(["billing", "technical", "account", "general"]);
export const ClassificationResult = z.object({
  intent: Intent,
  confidence: z.number().min(0).max(1),
  reasoning: z.string(),
});
export const TriageRequest = z.object({
  message: z.string().min(1),
  user_id: z.string().min(1),
});
export const TriageResponse = z.object({
  conversation_id: z.string(),
  intent: z.string(),
  specialist_response: z.string(),
  escalated: z.boolean(),
  trace_id: z.string(),
});
```

## API Contract

### `POST /triage`

Classify a customer message and route to a specialist.

**Request:**

```json
{
  "message": "I was charged twice for my subscription last month",
  "user_id": "user-456"
}
```

**Response (200):**

```json
{
  "conversation_id": "c1d2e3f4-...",
  "intent": "billing",
  "specialist_response": "I understand you're concerned about a duplicate charge. Let me look into your billing history...",
  "escalated": false,
  "trace_id": "a1b2c3d4-..."
}
```

**Escalation (200) — low confidence:**

```json
{
  "conversation_id": "c1d2e3f4-...",
  "intent": "general",
  "specialist_response": "Escalated to human agent due to low classification confidence.",
  "escalated": true,
  "trace_id": "a1b2c3d4-..."
}
```

**Errors:**

| Status | Body | When |
|--------|------|------|
| 400 | `{"error": "Invalid request", "details": [...]}` | Empty message |
| 500 | `{"error": "Internal error"}` | LLM or service failure |

### `GET /health`

Returns `{"status": "ok"}`.

## Tool Specifications

### `lookup_billing`

| Field | Value |
|-------|-------|
| **Description** | Look up billing information for a customer using Stripe. Returns subscription details, recent charges, and payment method info. |
| **Parameter** | `query` (string, required) — Billing-related query (e.g., "duplicate charge", "refund", "subscription"). |
| **Return type** | `string` — Formatted billing summary with customer info and relevant details. |

### `search_knowledge_base`

| Field | Value |
|-------|-------|
| **Description** | Search the knowledge base for articles relevant to the customer's question. Used by technical and account specialists. |
| **Parameter** | `query` (string, required) — The search query. |
| **Return type** | `string` — Top matching KB articles formatted with titles and content, separated by dividers. |

## Prompt Specifications

### Classifier

```
You are a customer support intent classifier.
Given a customer message, classify it into exactly one of these intents:
- billing: payment issues, subscription changes, invoices, charges, refunds
- technical: bugs, errors, API issues, integration problems, performance
- account: password resets, profile updates, access issues, account settings
- general: everything else, general questions, feedback, feature requests

Return the intent, your confidence (0.0 to 1.0), and brief reasoning.
```

**Design rationale:** The classifier uses structured output (`result_type=ClassificationResult` / `generateObject`) to guarantee a valid intent enum. The confidence score enables downstream gating — below `ESCALATION_THRESHOLD` (default 0.7), the request is escalated to a human.

### Specialist prompts

Each specialist has a focused system prompt:

- **Billing:** `"You are a billing support specialist. Help customers with payment issues, subscription changes, invoices, and charges. You have access to the Stripe tool to look up billing information."`
- **Technical:** `"You are a technical support specialist. Help customers with bugs, errors, API issues, and integration problems. You have access to a knowledge base search tool."`
- **Account:** `"You are an account support specialist. Help customers with password resets, profile updates, and account settings. You have access to a knowledge base search tool."`
- **General:** `"You are a general support specialist. Help customers with general questions, feedback, and feature requests."`

**Design rationale:** Each specialist only sees the tools relevant to its domain. The billing agent can call Stripe but not search the KB. This prevents tool misuse and keeps each specialist focused.

## Implementation Roadmap

| Step | Task | Key deliverables |
|------|------|-----------------|
| 1 | **Project scaffolding** | FastAPI/Hono app with `/health`, settings, structured logging |
| 2 | **Data models** | Pydantic + Zod schemas for Intent, ClassificationResult, request/response |
| 3 | **Database models** | Conversation and Message tables for logging |
| 4 | **Classifier agent** | Pydantic AI agent with `result_type=ClassificationResult` |
| 5 | **Tool implementations** | `lookup_billing` (mock Stripe), `search_knowledge_base` (mock KB) |
| 6 | **Specialist agents** | 4 specialists, each with isolated tool set |
| 7 | **Triage router** | Classify → check confidence → route to specialist or escalate |
| 8 | **API endpoint** | `POST /triage` with conversation logging |
| 9 | **Cross-cutting** | JWT auth, rate limiting, Langfuse tracing |
| 10 | **Unit tests** | Classification schema, routing logic, tool mocks |
| 11 | **Integration + eval** | End-to-end triage with real LLM, promptfoo security scan |

## Environment & Deployment

### Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `CLASSIFIER_MODEL` | No | `claude-haiku-4-5-20251001` | Model for classification (cheaper) |
| `SPECIALIST_MODEL` | No | `claude-sonnet-4-6-20250514` | Model for specialist responses |
| `ESCALATION_THRESHOLD` | No | `0.7` | Min confidence to auto-route (below = escalate) |
| `DATABASE_URL` | No | `postgresql+asyncpg://agent:agent@localhost:5432/agent_db` | Postgres connection |
| `REDIS_URL` | No | `redis://localhost:6379` | Redis for rate limiting |
| `QDRANT_URL` | No | `http://localhost:6333` | Qdrant for KB search |
| `LANGFUSE_PUBLIC_KEY` | No | `pk-lf-local` | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | No | `sk-lf-local` | Langfuse secret key |
| `LANGFUSE_HOST` | No | `http://localhost:3000` | Langfuse server URL |
| `JWT_SECRET` | No | `change-me-in-production` | JWT signing secret |
| `APP_ENV` | No | `development` | Environment name |
| `LOG_LEVEL` | No | `INFO` | Log level |

### Docker Compose

See [Docker Compose template](../reference/docker-compose-template.md) for base infrastructure. This agent needs: Postgres, Redis, Qdrant, Langfuse.

### Infrastructure dependencies

| Component | Required? | Why |
|-----------|-----------|-----|
| Postgres | Yes | Conversation logging and triage history |
| Redis | Yes | Rate limiting backend |
| Qdrant | Optional | Knowledge base vector search (can start with in-memory keyword search) |
| Langfuse | Recommended | LLM + tool call tracing (skip for local dev) |

## Test Strategy

### Unit tests

```python
def test_classification_returns_valid_intent(mock_llm_client):
    """Classifier always returns a valid Intent enum value."""
    result = await classify_intent("I need a refund")
    assert result.intent in ["billing", "technical", "account", "general"]
    assert 0 <= result.confidence <= 1

def test_low_confidence_triggers_escalation():
    """Below ESCALATION_THRESHOLD, request is escalated."""
    # Mock classifier to return confidence=0.3
    # Assert response.escalated == True

def test_billing_specialist_uses_stripe_tool(mock_llm_client):
    """Billing specialist calls lookup_billing, not search_knowledge_base."""
    result = await run_specialist("billing", "I was charged twice")
    tool_names = [tc.tool_name for tc in result.tool_calls]
    assert "lookup_billing" in tool_names
```

### Eval assertions

- Classification accuracy ≥ 90% on the 51-example dataset
- Billing queries always trigger `lookup_billing` tool
- Technical queries always trigger `search_knowledge_base` tool
- No prompt injection bypasses the classifier (promptfoo red-team)

## Eval Dataset

See the inline `eval/dataset.jsonl` (51 examples) in the Reference Implementation section below. Covers all 4 intents with ~12 examples each.

## Design decisions

- **Separate classifier and specialist models:** The classifier can use a cheaper/faster model since it only needs to produce structured classification. Specialists use the full model for nuanced responses.
- **Pydantic AI `result_type` for classification:** Structured output validation ensures the classifier always returns a valid intent enum, not a free-text guess.
- **Isolated specialist agents:** Each specialist has only its own tools. The billing agent can't accidentally search the KB, and the technical agent can't call Stripe. This prevents tool misuse.
- **Confidence score:** The classifier returns a confidence score, enabling future gating (e.g., fall back to general handler below 0.7 confidence).

## Reference Implementation

### Python

<details>
<summary><code>app/main.py</code></summary>

```python
"""FastAPI entrypoint for customer-support-triage."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api.triage import router as triage_router
from app.db.models import Base
from app.db.session import engine
from app.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    from agent_common.logs import configure

    configure(settings.app_name, env=settings.app_env, log_level=settings.log_level)

    logger = structlog.get_logger()
    logger.info("starting", app=settings.app_name)

    # Create tables (use Alembic in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)

app.include_router(triage_router)


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
    app_name: str = "customer-support-triage"
    app_env: str = "development"
    log_level: str = "INFO"

    # LLM
    anthropic_api_key: str = ""
    classifier_model: str = "claude-haiku-4-5-20251001"
    specialist_model: str = "claude-sonnet-4-6-20250514"

    # Routing
    escalation_threshold: float = 0.7

    # Database
    database_url: str = "postgresql+asyncpg://agent:agent@localhost:5432/agent_db"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "support_kb"

    # Auth
    jwt_secret: str = "change-me-in-production"

    # Langfuse
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
"""Request/response schemas and domain types."""

from enum import Enum

from pydantic import BaseModel


class Intent(str, Enum):
    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    GENERAL = "general"


class ClassificationResult(BaseModel):
    intent: Intent
    confidence: float
    reasoning: str


class TriageRequest(BaseModel):
    message: str
    user_id: str


class TriageResponse(BaseModel):
    conversation_id: str
    intent: str
    specialist_response: str
    escalated: bool
    trace_id: str


class ConversationOut(BaseModel):
    id: str
    user_id: str
    created_at: str
    resolved_at: str | None
    escalated: bool
    messages: list["MessageOut"]


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    intent: str | None
    tool_calls: list[dict] | None
    created_at: str
```

</details>

<details>
<summary><code>app/agent/classifier.py</code></summary>

```python
"""Intent classifier using Pydantic AI with structured output."""

from pydantic_ai import Agent

from app.models.schemas import ClassificationResult
from app.settings import settings

CLASSIFIER_SYSTEM_PROMPT = """You are a customer support intent classifier.
Given a customer message, classify it into exactly one of these intents:
- billing: payment issues, subscription changes, invoices, charges, refunds
- technical: bugs, errors, API issues, integration problems, performance
- account: password resets, profile updates, access issues, account settings
- general: everything else, general questions, feedback, feature requests

Return the intent, your confidence (0.0 to 1.0), and brief reasoning."""

_classifier_agent: Agent | None = None


def _get_classifier() -> Agent:
    global _classifier_agent
    if _classifier_agent is None:
        _classifier_agent = Agent(
            f"anthropic:{settings.classifier_model}",
            result_type=ClassificationResult,
            system_prompt=CLASSIFIER_SYSTEM_PROMPT,
        )
    return _classifier_agent


async def classify_intent(message: str) -> ClassificationResult:
    """Classify a customer message into an intent category."""
    agent = _get_classifier()
    result = await agent.run(message)
    return result.data
```

</details>

<details>
<summary><code>app/agent/specialists.py</code></summary>

```python
"""Specialist agents for each intent category."""

from pydantic_ai import Agent

from app.models.schemas import Intent
from app.settings import settings
from app.tools.kb import kb_search
from app.tools.stripe import stripe_lookup

SPECIALIST_PROMPTS = {
    Intent.BILLING: """You are a billing support specialist. Help customers with payment issues,
subscription changes, invoices, and charges. You have access to the Stripe tool to look up
billing information. Be helpful, concise, and professional.""",
    Intent.TECHNICAL: """You are a technical support specialist. Help customers with bugs, errors,
API issues, and integration problems. You have access to a knowledge base search tool.
Provide clear, actionable guidance.""",
    Intent.ACCOUNT: """You are an account support specialist. Help customers with password resets,
profile updates, and account settings. You have access to a knowledge base search tool.
Guide them step by step.""",
    Intent.GENERAL: """You are a general support specialist. Help customers with general questions,
feedback, and feature requests. Be friendly and helpful.""",
}


def _make_billing_agent() -> Agent:
    agent = Agent(
        f"anthropic:{settings.specialist_model}",
        system_prompt=SPECIALIST_PROMPTS[Intent.BILLING],
    )

    @agent.tool_plain
    async def lookup_billing(query: str) -> str:
        """Look up billing information for a customer using Stripe."""
        return await stripe_lookup(query)

    return agent


def _make_technical_agent() -> Agent:
    agent = Agent(
        f"anthropic:{settings.specialist_model}",
        system_prompt=SPECIALIST_PROMPTS[Intent.TECHNICAL],
    )

    @agent.tool_plain
    async def search_knowledge_base(query: str) -> str:
        """Search the technical knowledge base for relevant articles."""
        return await kb_search(query)

    return agent


def _make_account_agent() -> Agent:
    agent = Agent(
        f"anthropic:{settings.specialist_model}",
        system_prompt=SPECIALIST_PROMPTS[Intent.ACCOUNT],
    )

    @agent.tool_plain
    async def search_knowledge_base(query: str) -> str:
        """Search the account knowledge base for relevant articles."""
        return await kb_search(query)

    return agent


def _make_general_agent() -> Agent:
    return Agent(
        f"anthropic:{settings.specialist_model}",
        system_prompt=SPECIALIST_PROMPTS[Intent.GENERAL],
    )


_agents: dict[Intent, Agent] = {}


def get_specialist(intent: Intent) -> Agent:
    """Get the specialist agent for a given intent (lazy-initialized)."""
    if intent not in _agents:
        factories = {
            Intent.BILLING: _make_billing_agent,
            Intent.TECHNICAL: _make_technical_agent,
            Intent.ACCOUNT: _make_account_agent,
            Intent.GENERAL: _make_general_agent,
        }
        _agents[intent] = factories[intent]()
    return _agents[intent]


async def run_specialist(intent: Intent, message: str) -> tuple[str, list[dict]]:
    """Run the specialist agent and return (response_text, tool_calls)."""
    agent = get_specialist(intent)
    result = await agent.run(message)
    tool_calls = [
        {"tool_name": call.tool_name, "args": call.args}
        for call in result.all_messages()
        if hasattr(call, "tool_name")
    ]
    return result.data, tool_calls
```

</details>

<details>
<summary><code>app/api/triage.py</code></summary>

```python
"""Triage and conversation route handlers."""

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.classifier import classify_intent
from app.agent.specialists import run_specialist
from app.db.models import Conversation, Message
from app.db.session import get_session
from app.models.schemas import (
    ConversationOut,
    MessageOut,
    TriageRequest,
    TriageResponse,
)
from app.settings import settings

logger = structlog.get_logger()

router = APIRouter()


@router.post("/triage", response_model=TriageResponse)
async def triage(
    request: TriageRequest,
    session: AsyncSession = Depends(get_session),
):
    """Classify intent, route to specialist, return resolution."""
    trace_id = str(uuid.uuid4())
    log = logger.bind(trace_id=trace_id, user_id=request.user_id)

    # Create conversation
    conversation = Conversation(user_id=request.user_id)
    session.add(conversation)

    # Store user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    session.add(user_msg)

    # Classify intent
    log.info("classifying_intent")
    classification = await classify_intent(request.message)
    log.info("intent_classified", intent=classification.intent, confidence=classification.confidence)

    user_msg.intent = classification.intent.value

    # Check escalation threshold
    if classification.confidence < settings.escalation_threshold:
        log.info("escalating", reason="low_confidence", confidence=classification.confidence)
        conversation.escalated = True
        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=(
                "I'm not fully confident in my assessment. "
                "Let me connect you with a human agent who can better assist you."
            ),
            intent=classification.intent.value,
        )
        session.add(assistant_msg)
        await session.commit()

        return TriageResponse(
            conversation_id=conversation.id,
            intent=classification.intent.value,
            specialist_response="Escalated to human agent due to low classification confidence.",
            escalated=True,
            trace_id=trace_id,
        )

    # Route to specialist
    log.info("routing_to_specialist", intent=classification.intent)
    response_text, tool_calls = await run_specialist(classification.intent, request.message)
    log.info("specialist_responded", tool_calls_count=len(tool_calls))

    # Store assistant response
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=response_text,
        intent=classification.intent.value,
        tool_calls_json=tool_calls if tool_calls else None,
    )
    session.add(assistant_msg)

    conversation.resolved_at = datetime.now(UTC)
    await session.commit()

    return TriageResponse(
        conversation_id=conversation.id,
        intent=classification.intent.value,
        specialist_response=response_text,
        escalated=False,
        trace_id=trace_id,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Fetch a conversation with its messages."""
    result = await session.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationOut(
        id=conversation.id,
        user_id=conversation.user_id,
        created_at=conversation.created_at.isoformat(),
        resolved_at=conversation.resolved_at.isoformat() if conversation.resolved_at else None,
        escalated=conversation.escalated,
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                intent=m.intent,
                tool_calls=m.tool_calls_json,
                created_at=m.created_at.isoformat(),
            )
            for m in conversation.messages
        ],
    )
```

</details>

<details>
<summary><code>app/tools/kb.py</code></summary>

```python
"""Knowledge base search tool using Qdrant.

Falls back to mock data when Qdrant is unavailable, making the prototype
runnable without the full infra stack for development and testing.
"""

import structlog

logger = structlog.get_logger()

# Mock KB articles for when Qdrant is unavailable
_MOCK_KB = [
    {
        "id": "kb-001",
        "title": "How to reset your password",
        "content": (
            "Go to Settings > Security > Reset Password. Enter your current"
            " password, then your new password twice. Click Save. You'll"
            " receive a confirmation email."
        ),
        "category": "account",
    },
    {
        "id": "kb-002",
        "title": "API rate limits and error codes",
        "content": (
            "Rate limits: 100 requests/minute for free tier, 1000/minute"
            " for Pro. When exceeded, you'll get a 429 status code."
            " Implement exponential backoff. Common errors: 400 (bad"
            " request), 401 (unauthorized), 500 (server error —"
            " contact support)."
        ),
        "category": "technical",
    },
    {
        "id": "kb-003",
        "title": "Updating your billing information",
        "content": (
            "Navigate to Account > Billing > Payment Methods. Click"
            " 'Update' next to your current method. Enter new card"
            " details. Changes take effect on your next billing cycle."
        ),
        "category": "billing",
    },
    {
        "id": "kb-004",
        "title": "Troubleshooting large payload errors",
        "content": (
            "Maximum payload size is 10MB for the standard API. For"
            " larger payloads, use the streaming endpoint or split your"
            " request. If you're getting 500 errors, check that your"
            " Content-Type header is set correctly and the JSON is valid."
        ),
        "category": "technical",
    },
    {
        "id": "kb-005",
        "title": "Two-factor authentication setup",
        "content": (
            "Go to Settings > Security > 2FA. Choose your method:"
            " authenticator app (recommended) or SMS. Scan the QR code"
            " with your authenticator app. Enter the 6-digit code to"
            " verify. Save your backup codes in a secure location."
        ),
        "category": "account",
    },
    {
        "id": "kb-006",
        "title": "Integration webhook configuration",
        "content": (
            "Set up webhooks at Settings > Integrations > Webhooks. Add"
            " your endpoint URL, select events to subscribe to, and save."
            " We'll send a test ping. Webhook payloads are signed with"
            " your webhook secret for verification."
        ),
        "category": "technical",
    },
]


async def kb_search(query: str, top_k: int = 3) -> str:
    """Search the knowledge base. Falls back to keyword matching if Qdrant is unavailable."""
    try:
        return await _qdrant_search(query, top_k)
    except Exception:
        logger.info("qdrant_unavailable_using_mock", query=query)
        return _mock_search(query, top_k)


async def _qdrant_search(query: str, top_k: int) -> str:
    """Search using Qdrant vector DB."""
    from qdrant_client import AsyncQdrantClient

    from app.settings import settings

    client = AsyncQdrantClient(url=settings.qdrant_url)

    collections = await client.get_collections()
    collection_names = [c.name for c in collections.collections]
    if settings.qdrant_collection not in collection_names:
        raise RuntimeError("Collection not found")

    results = await client.query(
        collection_name=settings.qdrant_collection,
        query_text=query,
        limit=top_k,
    )

    if not results:
        return "No relevant articles found in the knowledge base."

    articles = []
    for point in results:
        payload = point.metadata
        articles.append(f"**{payload.get('title', 'Untitled')}**\n{payload.get('content', '')}")

    return "\n\n---\n\n".join(articles)


def _mock_search(query: str, top_k: int) -> str:
    """Simple keyword-based fallback search."""
    query_lower = query.lower()
    scored = []
    for article in _MOCK_KB:
        score = sum(
            1
            for word in query_lower.split()
            if word in article["title"].lower() or word in article["content"].lower()
        )
        if score > 0:
            scored.append((score, article))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    if not top:
        return "No relevant articles found in the knowledge base."

    articles = [f"**{a['title']}**\n{a['content']}" for _, a in top]
    return "\n\n---\n\n".join(articles)
```

</details>

<details>
<summary><code>app/tools/stripe.py</code></summary>

```python
"""Mock Stripe MCP tool for billing lookups.

In production, this would connect to a real Stripe MCP server.
The mock returns realistic responses for demo and eval purposes.
"""

import json

_MOCK_CUSTOMERS = {
    "default": {
        "customer_id": "cus_demo123",
        "email": "customer@example.com",
        "plan": "Pro",
        "monthly_amount": "$49.00",
        "status": "active",
        "last_payment": "2026-04-01",
        "next_billing": "2026-05-01",
        "payment_method": "Visa ending in 4242",
    }
}

_MOCK_RESPONSES = {
    "charge": (
        "Found recent charge of $49.00 on 2026-04-01 for Pro plan"
        " subscription. Status: succeeded. No duplicate charges detected."
    ),
    "refund": (
        "Refund policy: Full refunds available within 30 days of charge."
        " To process a refund, the customer should confirm the charge"
        " date and amount."
    ),
    "subscription": (
        "Current subscription: Pro plan at $49.00/month. Next billing"
        " date: 2026-05-01. Plan can be changed or cancelled from"
        " account settings."
    ),
    "invoice": (
        "Most recent invoice #INV-2026-0401 for $49.00 issued on"
        " 2026-04-01. Status: paid. PDF available at billing portal."
    ),
    "payment_method": (
        "Current payment method: Visa ending in 4242, expiring 12/2027."
        " To update, customer can visit the billing portal."
    ),
}


async def stripe_lookup(query: str) -> str:
    """Look up billing information. Returns a structured response string."""
    query_lower = query.lower()

    for keyword, response in _MOCK_RESPONSES.items():
        if keyword in query_lower:
            customer = _MOCK_CUSTOMERS["default"]
            return f"Customer: {customer['email']} ({customer['customer_id']})\n{response}"

    customer = _MOCK_CUSTOMERS["default"]
    return f"Customer billing summary:\n{json.dumps(customer, indent=2)}"
```

</details>

<details>
<summary><code>app/db/models.py</code></summary>

```python
"""SQLAlchemy models for conversations and messages."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    escalated = Column(Boolean, default=False)

    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    intent = Column(String, nullable=True)
    tool_calls_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    conversation = relationship("Conversation", back_populates="messages")
```

</details>

<details>
<summary><code>app/db/session.py</code></summary>

```python
"""Database session management."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.settings import settings

engine = create_async_engine(settings.database_url, echo=settings.app_env == "development")
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
```

</details>

### TypeScript

<details>
<summary><code>src/index.ts</code></summary>

```typescript
import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { triageRouter } from "./api/triage.js";

const app = new Hono();

app.get("/health", (c) => c.json({ status: "ok" }));
app.route("/", triageRouter);

const port = Number(process.env.PORT ?? 8000);

serve({ fetch: app.fetch, port }, (info) => {
  console.log(
    `customer-support-triage running at http://localhost:${info.port}`,
  );
});

export default app;
```

</details>

<details>
<summary><code>src/config.ts</code></summary>

```typescript
import { z } from "zod";

const configSchema = z.object({
  appName: z.string().default("customer-support-triage"),
  appEnv: z.string().default("development"),
  logLevel: z.string().default("info"),

  anthropicApiKey: z.string().default(""),
  classifierModel: z.string().default("claude-haiku-4-5-20251001"),
  specialistModel: z.string().default("claude-sonnet-4-6-20250514"),

  escalationThreshold: z.coerce.number().default(0.7),

  databaseUrl: z
    .string()
    .default("postgresql://agent:agent@localhost:5432/agent_db"),
  redisUrl: z.string().default("redis://localhost:6379"),
  qdrantUrl: z.string().default("http://localhost:6333"),

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
  classifierModel: process.env.CLASSIFIER_MODEL,
  specialistModel: process.env.SPECIALIST_MODEL,
  escalationThreshold: process.env.ESCALATION_THRESHOLD,
  databaseUrl: process.env.DATABASE_URL,
  redisUrl: process.env.REDIS_URL,
  qdrantUrl: process.env.QDRANT_URL,
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

export const Intent = z.enum(["billing", "technical", "account", "general"]);
export type Intent = z.infer<typeof Intent>;

export const ClassificationResult = z.object({
  intent: Intent,
  confidence: z.number().min(0).max(1),
  reasoning: z.string(),
});
export type ClassificationResult = z.infer<typeof ClassificationResult>;

export const TriageRequest = z.object({
  message: z.string().min(1),
  user_id: z.string().min(1),
});
export type TriageRequest = z.infer<typeof TriageRequest>;

export const TriageResponse = z.object({
  conversation_id: z.string(),
  intent: z.string(),
  specialist_response: z.string(),
  escalated: z.boolean(),
  trace_id: z.string(),
});
export type TriageResponse = z.infer<typeof TriageResponse>;
```

</details>

<details>
<summary><code>src/agent/classifier.ts</code></summary>

```typescript
/**
 * Intent classifier using Vercel AI SDK with structured output.
 */

import { anthropic } from "@ai-sdk/anthropic";
import { generateObject } from "ai";
import { config } from "../config.js";
import { ClassificationResult } from "../schemas/index.js";

const CLASSIFIER_SYSTEM_PROMPT = `You are a customer support intent classifier.
Given a customer message, classify it into exactly one of these intents:
- billing: payment issues, subscription changes, invoices, charges, refunds
- technical: bugs, errors, API issues, integration problems, performance
- account: password resets, profile updates, access issues, account settings
- general: everything else, general questions, feedback, feature requests

Return the intent, your confidence (0.0 to 1.0), and brief reasoning.`;

export async function classifyIntent(
  message: string,
): Promise<{ intent: string; confidence: number; reasoning: string }> {
  const result = await generateObject({
    model: anthropic(config.classifierModel),
    schema: ClassificationResult,
    system: CLASSIFIER_SYSTEM_PROMPT,
    prompt: message,
  });

  return result.object;
}
```

</details>

<details>
<summary><code>src/agent/specialists.ts</code></summary>

```typescript
/**
 * Specialist agents for each intent category.
 */

import { anthropic } from "@ai-sdk/anthropic";
import { generateText, tool } from "ai";
import { z } from "zod";
import { config } from "../config.js";
import { kbSearch } from "../tools/kb.js";
import { stripeLookup } from "../tools/stripe.js";

const SPECIALIST_PROMPTS: Record<string, string> = {
  billing: `You are a billing support specialist. Help customers with payment issues,
subscription changes, invoices, and charges. You have access to the Stripe tool to look up
billing information. Be helpful, concise, and professional.`,
  technical: `You are a technical support specialist. Help customers with bugs, errors,
API issues, and integration problems. You have access to a knowledge base search tool.
Provide clear, actionable guidance.`,
  account: `You are an account support specialist. Help customers with password resets,
profile updates, and account settings. You have access to a knowledge base search tool.
Guide them step by step.`,
  general: `You are a general support specialist. Help customers with general questions,
feedback, and feature requests. Be friendly and helpful.`,
};

const billingTools = {
  lookup_billing: tool({
    description: "Look up billing information for a customer using Stripe",
    parameters: z.object({ query: z.string() }),
    execute: async ({ query }) => stripeLookup(query),
  }),
};

const kbTools = {
  search_knowledge_base: tool({
    description: "Search the knowledge base for relevant articles",
    parameters: z.object({ query: z.string() }),
    execute: async ({ query }) => kbSearch(query),
  }),
};

const SPECIALIST_TOOLS: Record<string, typeof billingTools | typeof kbTools> = {
  billing: billingTools,
  technical: kbTools,
  account: kbTools,
};

export async function runSpecialist(
  intent: string,
  message: string,
): Promise<{
  text: string;
  toolCalls: Array<{ toolName: string; args: Record<string, unknown> }>;
}> {
  const systemPrompt = SPECIALIST_PROMPTS[intent] ?? SPECIALIST_PROMPTS.general;
  const tools = SPECIALIST_TOOLS[intent] ?? undefined;

  const result = await generateText({
    model: anthropic(config.specialistModel),
    system: systemPrompt,
    prompt: message,
    tools,
    maxSteps: 3,
  });

  const toolCalls = result.steps
    .flatMap((s) => s.toolCalls)
    .map((tc: { toolName: string; args: unknown }) => ({
      toolName: tc.toolName,
      args: tc.args as Record<string, unknown>,
    }));

  return { text: result.text, toolCalls };
}
```

</details>

<details>
<summary><code>src/api/triage.ts</code></summary>

```typescript
/**
 * Triage route handler.
 */

import { Hono } from "hono";
import { classifyIntent } from "../agent/classifier.js";
import { runSpecialist } from "../agent/specialists.js";
import { config } from "../config.js";
import { TriageRequest } from "../schemas/index.js";

export const triageRouter = new Hono();

triageRouter.post("/triage", async (c) => {
  const body = await c.req.json();
  const parsed = TriageRequest.safeParse(body);

  if (!parsed.success) {
    return c.json(
      { error: "Invalid request", details: parsed.error.issues },
      400,
    );
  }

  const { message, user_id } = parsed.data;
  const traceId = crypto.randomUUID();
  const conversationId = crypto.randomUUID();

  // Classify intent
  const classification = await classifyIntent(message);

  // Check escalation threshold
  if (classification.confidence < config.escalationThreshold) {
    return c.json({
      conversation_id: conversationId,
      intent: classification.intent,
      specialist_response:
        "Escalated to human agent due to low classification confidence.",
      escalated: true,
      trace_id: traceId,
    });
  }

  // Route to specialist
  const { text, toolCalls } = await runSpecialist(
    classification.intent,
    message,
  );

  return c.json({
    conversation_id: conversationId,
    intent: classification.intent,
    specialist_response: text,
    escalated: false,
    trace_id: traceId,
  });
});
```

</details>

<details>
<summary><code>src/tools/kb.ts</code></summary>

```typescript
/**
 * Knowledge base search tool. Falls back to mock data when Qdrant is unavailable.
 */

interface KBArticle {
  id: string;
  title: string;
  content: string;
  category: string;
}

const MOCK_KB: KBArticle[] = [
  {
    id: "kb-001",
    title: "How to reset your password",
    content:
      "Go to Settings > Security > Reset Password. Enter your current password, then your new password twice. Click Save.",
    category: "account",
  },
  {
    id: "kb-002",
    title: "API rate limits and error codes",
    content:
      "Rate limits: 100 req/min for free, 1000/min for Pro. 429 = rate limited. Common: 400 (bad request), 401 (unauthorized), 500 (server error).",
    category: "technical",
  },
  {
    id: "kb-003",
    title: "Updating your billing information",
    content:
      "Navigate to Account > Billing > Payment Methods. Click Update next to your current method. Enter new card details.",
    category: "billing",
  },
  {
    id: "kb-004",
    title: "Troubleshooting large payload errors",
    content:
      "Maximum payload size is 10MB. For larger payloads, use streaming or split requests. Check Content-Type header and JSON validity.",
    category: "technical",
  },
  {
    id: "kb-005",
    title: "Two-factor authentication setup",
    content:
      "Go to Settings > Security > 2FA. Choose authenticator app or SMS. Scan QR code. Enter 6-digit code to verify. Save backup codes.",
    category: "account",
  },
  {
    id: "kb-006",
    title: "Integration webhook configuration",
    content:
      "Set up at Settings > Integrations > Webhooks. Add endpoint URL, select events, save. Payloads are signed with your webhook secret.",
    category: "technical",
  },
];

export function mockSearch(query: string, topK = 3): string {
  const words = query.toLowerCase().split(/\s+/);
  const scored: Array<[number, KBArticle]> = [];

  for (const article of MOCK_KB) {
    const text = `${article.title} ${article.content}`.toLowerCase();
    const score = words.filter((w) => text.includes(w)).length;
    if (score > 0) scored.push([score, article]);
  }

  scored.sort((a, b) => b[0] - a[0]);
  const top = scored.slice(0, topK);

  if (top.length === 0)
    return "No relevant articles found in the knowledge base.";

  return top.map(([, a]) => `**${a.title}**\n${a.content}`).join("\n\n---\n\n");
}

export async function kbSearch(query: string, topK = 3): Promise<string> {
  return mockSearch(query, topK);
}
```

</details>

<details>
<summary><code>src/tools/stripe.ts</code></summary>

```typescript
/**
 * Mock Stripe tool for billing lookups.
 */

const MOCK_CUSTOMER = {
  customer_id: "cus_demo123",
  email: "customer@example.com",
  plan: "Pro",
  monthly_amount: "$49.00",
  status: "active",
  last_payment: "2026-04-01",
  next_billing: "2026-05-01",
  payment_method: "Visa ending in 4242",
};

const MOCK_RESPONSES: Record<string, string> = {
  charge:
    "Found recent charge of $49.00 on 2026-04-01 for Pro plan subscription. Status: succeeded. No duplicate charges detected.",
  refund:
    "Refund policy: Full refunds available within 30 days of charge. To process a refund, the customer should confirm the charge date and amount.",
  subscription:
    "Current subscription: Pro plan at $49.00/month. Next billing date: 2026-05-01. Plan can be changed or cancelled from account settings.",
  invoice:
    "Most recent invoice #INV-2026-0401 for $49.00 issued on 2026-04-01. Status: paid. PDF available at billing portal.",
  payment_method:
    "Current payment method: Visa ending in 4242, expiring 12/2027. To update, customer can visit the billing portal.",
};

export async function stripeLookup(query: string): Promise<string> {
  const q = query.toLowerCase();

  for (const [keyword, response] of Object.entries(MOCK_RESPONSES)) {
    if (q.includes(keyword)) {
      return `Customer: ${MOCK_CUSTOMER.email} (${MOCK_CUSTOMER.customer_id})\n${response}`;
    }
  }

  return `Customer billing summary:\n${JSON.stringify(MOCK_CUSTOMER, null, 2)}`;
}
```

</details>

### Configuration & Eval

<details>
<summary><code>.env.example</code></summary>

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# LLM models (defaults are fine for local dev)
# CLASSIFIER_MODEL=claude-haiku-4-5-20251001
# SPECIALIST_MODEL=claude-sonnet-4-6-20250514

# Routing
# ESCALATION_THRESHOLD=0.7

# Postgres
POSTGRES_USER=agent
POSTGRES_PASSWORD=agent
POSTGRES_DB=agent_db
DATABASE_URL=postgresql+asyncpg://agent:agent@postgres:5432/agent_db

# Redis
REDIS_URL=redis://redis:6379

# Qdrant
QDRANT_URL=http://qdrant:6333

# Langfuse
LANGFUSE_PUBLIC_KEY=pk-lf-local
LANGFUSE_SECRET_KEY=sk-lf-local
LANGFUSE_HOST=http://langfuse:3000

# Auth
JWT_SECRET=change-me-in-production

# App
APP_ENV=development
LOG_LEVEL=INFO
```

</details>

<details>
<summary><code>eval/dataset.jsonl</code> (51 examples)</summary>

```jsonl
{"input": "I was charged twice for my subscription this month", "expected_intent": "billing", "expected_tool": "lookup_billing"}
{"input": "Can you help me get a refund for last month?", "expected_intent": "billing", "expected_tool": "lookup_billing"}
{"input": "What payment methods do you accept?", "expected_intent": "billing", "expected_tool": "lookup_billing"}
{"input": "My invoice shows the wrong amount", "expected_intent": "billing", "expected_tool": "lookup_billing"}
{"input": "I want to upgrade my subscription plan", "expected_intent": "billing", "expected_tool": "lookup_billing"}
{"input": "When is my next billing date?", "expected_intent": "billing", "expected_tool": "lookup_billing"}
{"input": "I need to update my credit card on file", "expected_intent": "billing", "expected_tool": "lookup_billing"}
{"input": "Why was I charged $99 instead of $49?", "expected_intent": "billing", "expected_tool": "lookup_billing"}
{"input": "Can I get a receipt for my last payment?", "expected_intent": "billing", "expected_tool": "lookup_billing"}
{"input": "I want to cancel my subscription", "expected_intent": "billing", "expected_tool": "lookup_billing"}
{"input": "How do I downgrade to the free plan?", "expected_intent": "billing", "expected_tool": "lookup_billing"}
{"input": "Is there a discount for annual billing?", "expected_intent": "billing", "expected_tool": "lookup_billing"}
{"input": "The API returns 500 errors when I send large payloads", "expected_intent": "technical", "expected_tool": "search_knowledge_base"}
{"input": "I'm getting a 429 rate limit error", "expected_intent": "technical", "expected_tool": "search_knowledge_base"}
{"input": "How do I authenticate with the API?", "expected_intent": "technical", "expected_tool": "search_knowledge_base"}
{"input": "The webhook integration isn't working", "expected_intent": "technical", "expected_tool": "search_knowledge_base"}
{"input": "What's the maximum payload size for the API?", "expected_intent": "technical", "expected_tool": "search_knowledge_base"}
{"input": "I'm getting CORS errors in the browser", "expected_intent": "technical", "expected_tool": "search_knowledge_base"}
{"input": "The SDK throws a timeout exception after 30 seconds", "expected_intent": "technical", "expected_tool": "search_knowledge_base"}
{"input": "How do I set up webhooks for my integration?", "expected_intent": "technical", "expected_tool": "search_knowledge_base"}
{"input": "My API key stopped working suddenly", "expected_intent": "technical", "expected_tool": "search_knowledge_base"}
{"input": "Is there a sandbox environment for testing?", "expected_intent": "technical", "expected_tool": "search_knowledge_base"}
{"input": "The response format changed and broke my parser", "expected_intent": "technical", "expected_tool": "search_knowledge_base"}
{"input": "How do I handle pagination in the list endpoint?", "expected_intent": "technical", "expected_tool": "search_knowledge_base"}
{"input": "I need to reset my password", "expected_intent": "account", "expected_tool": "search_knowledge_base"}
{"input": "How do I enable two-factor authentication?", "expected_intent": "account", "expected_tool": "search_knowledge_base"}
{"input": "I want to change my email address", "expected_intent": "account", "expected_tool": "search_knowledge_base"}
{"input": "How do I delete my account?", "expected_intent": "account", "expected_tool": "search_knowledge_base"}
{"input": "I can't log in to my account", "expected_intent": "account", "expected_tool": "search_knowledge_base"}
{"input": "How do I add a team member to my organization?", "expected_intent": "account", "expected_tool": "search_knowledge_base"}
{"input": "I want to update my profile information", "expected_intent": "account", "expected_tool": "search_knowledge_base"}
{"input": "How do I change my notification preferences?", "expected_intent": "account", "expected_tool": "search_knowledge_base"}
{"input": "I forgot my username", "expected_intent": "account", "expected_tool": "search_knowledge_base"}
{"input": "How do I revoke API keys from my account?", "expected_intent": "account", "expected_tool": "search_knowledge_base"}
{"input": "Can I transfer ownership of my account?", "expected_intent": "account", "expected_tool": "search_knowledge_base"}
{"input": "My account was locked after too many login attempts", "expected_intent": "account", "expected_tool": "search_knowledge_base"}
{"input": "What features are included in the Pro plan?", "expected_intent": "general", "expected_tool": null}
{"input": "Do you have a mobile app?", "expected_intent": "general", "expected_tool": null}
{"input": "I'd like to request a new feature", "expected_intent": "general", "expected_tool": null}
{"input": "What's on your product roadmap?", "expected_intent": "general", "expected_tool": null}
{"input": "How does your product compare to competitors?", "expected_intent": "general", "expected_tool": null}
{"input": "Can I schedule a demo?", "expected_intent": "general", "expected_tool": null}
{"input": "Where can I find your documentation?", "expected_intent": "general", "expected_tool": null}
{"input": "Do you offer enterprise plans?", "expected_intent": "general", "expected_tool": null}
{"input": "What's your uptime SLA?", "expected_intent": "general", "expected_tool": null}
{"input": "I love your product, keep up the great work!", "expected_intent": "general", "expected_tool": null}
{"input": "Do you have a partner program?", "expected_intent": "general", "expected_tool": null}
{"input": "Is there a community forum?", "expected_intent": "general", "expected_tool": null}
{"input": "I need help but I'm not sure who to talk to", "expected_intent": "general", "expected_tool": null}
{"input": "Can you tell me about your data privacy practices?", "expected_intent": "general", "expected_tool": null}
```

</details>

<details>
<summary><code>eval/promptfoo.yaml</code></summary>

```yaml
description: "Security scan for customer-support-triage"

prompts:
  - "{{message}}"

providers:
  - id: http
    config:
      url: http://localhost:8000/triage
      method: POST
      headers:
        Content-Type: application/json
      body:
        message: "{{message}}"
        user_id: "eval-user"

redteam:
  plugins:
    - prompt-injection
    - jailbreak
    - pii
```

</details>
