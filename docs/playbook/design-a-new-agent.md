# Playbook: Design a New Agent

Step-by-step workflow for composing a new agent from the knowledge in this repo. Works whether you're designing manually or loading these docs as AI context.

---

## Step 1: Define the problem

Before picking anything, write down:

- **What does the agent do?** (one sentence)
- **What inputs does it receive?** (user message, document, batch of records, etc.)
- **What outputs does it produce?** (answer, structured data, side effects, etc.)
- **What external systems does it touch?** (APIs, databases, file systems, etc.)
- **What's the latency budget?** (real-time chat vs. async batch)

## Step 2: Pick a pattern

The pattern determines the *shape* of your agent's reasoning and data flow.

| If your agent needs to... | Pattern | Doc |
|--------------------------|---------|-----|
| Answer questions from a knowledge base | RAG | [patterns/rag.md](../patterns/rag.md) |
| Decide-act-observe in a loop | ReAct | [patterns/react.md](../patterns/react.md) |
| Route input to specialist handlers | Routing + Tool Use | [patterns/routing-tool-use.md](../patterns/routing-tool-use.md) |
| Run a fixed sequence of LLM steps | Prompt Chaining | [patterns/prompt-chaining.md](../patterns/prompt-chaining.md) |
| Make a plan, execute steps, then reflect | Plan & Execute | [patterns/plan-execute-reflect.md](../patterns/plan-execute-reflect.md) |
| Process many items independently | Parallel Calls | [patterns/parallel-calls.md](../patterns/parallel-calls.md) |
| Remember things across sessions | Memory | [patterns/memory.md](../patterns/memory.md) |
| Coordinate peer agents | Multi-Agent (flat) | [patterns/multi-agent-flat.md](../patterns/multi-agent-flat.md) |
| Have a supervisor delegate to sub-agents | Multi-Agent (hierarchical) | [patterns/multi-agent-hierarchical.md](../patterns/multi-agent-hierarchical.md) |

**Composing patterns:** Many real agents combine patterns. A research assistant might use ReAct for its core loop but RAG for document retrieval within one of its tools. Pick the *primary* pattern, then layer in secondary ones as needed.

## Step 3: Pick a framework

The framework determines *how* you implement the pattern in code.

| Framework | Language | Best for | Doc |
|-----------|----------|----------|-----|
| LangGraph | Python | Stateful graphs, checkpointing, complex multi-step agents | [frameworks/langgraph.md](../frameworks/langgraph.md) |
| Pydantic AI | Python | Type-safe tool use, structured outputs, routing/classifier agents | [frameworks/pydantic-ai.md](../frameworks/pydantic-ai.md) |
| CrewAI | Python | Role-based multi-agent crews | [frameworks/crewai.md](../frameworks/crewai.md) |
| Mastra | TypeScript | All TS patterns -- workflows, memory, eval built in | [frameworks/mastra.md](../frameworks/mastra.md) |
| Vercel AI SDK | TypeScript | Lightweight tool use, streaming, web-facing agents | [frameworks/vercel-ai-sdk.md](../frameworks/vercel-ai-sdk.md) |

**Decision heuristic:** If you need checkpointing or complex graph state, use LangGraph. If you need type-safe structured outputs, use Pydantic AI. If you're in TypeScript, start with Mastra. Each framework doc has a "patterns it supports well" section.

## Step 4: Pick stack components

Load the stack docs relevant to your agent. Every agent needs at least:

| Slot | Default pick | Doc | Required? |
|------|-------------|-----|-----------|
| LLM | Claude Sonnet 4.6 | [stack/llm-claude.md](../stack/llm-claude.md) | Yes |
| API layer | FastAPI (Py) / Hono (TS) | [stack/api-fastapi.md](../stack/api-fastapi.md) or [api-hono.md](../stack/api-hono.md) | Yes |
| Relational DB | Postgres 16 | [stack/relational-postgres.md](../stack/relational-postgres.md) | Yes |
| Cache | Redis 7 | [stack/cache-redis.md](../stack/cache-redis.md) | Yes |
| Tracing | Langfuse | [stack/tracing-langfuse.md](../stack/tracing-langfuse.md) | Yes |
| Vector DB | Qdrant | [stack/vector-qdrant.md](../stack/vector-qdrant.md) | If using RAG |
| Eval | DeepEval + RAGAS + Promptfoo | [stack/eval-deepeval-ragas-promptfoo.md](../stack/eval-deepeval-ragas-promptfoo.md) | For CI |
| Tool protocol | MCP | [stack/tool-protocol-mcp.md](../stack/tool-protocol-mcp.md) | If exposing tools |

## Step 5: Apply cross-cutting concerns

These are shared across all blueprints. Load all five:

- [Auth (JWT)](../cross-cutting/auth-jwt.md)
- [Structured logging](../cross-cutting/logging-structured.md)
- [Observability (Langfuse)](../cross-cutting/observability.md)
- [Rate limiting](../cross-cutting/rate-limiting.md)
- [Testing strategy](../cross-cutting/testing-strategy.md)

## Step 6: Reference the closest recipe

Find the recipe that most closely matches your design. Use it as a starting point, not a constraint.

| Recipe | Pattern | Status | Doc |
|--------|---------|--------|-----|
| customer-support-triage | Routing + Tool Use | Implemented | [recipes/customer-support-triage.md](../recipes/customer-support-triage.md) |
| docs-rag-qa | RAG | Implemented | [recipes/docs-rag-qa.md](../recipes/docs-rag-qa.md) |
| research-assistant | ReAct | Implemented | [recipes/research-assistant.md](../recipes/research-assistant.md) |
| content-pipeline | Prompt Chaining | Skeleton | [recipes/content-pipeline.md](../recipes/content-pipeline.md) |
| code-review-agent | Plan & Execute | Skeleton | [recipes/code-review-agent.md](../recipes/code-review-agent.md) |
| ops-crew | Multi-Agent (flat) | Skeleton | [recipes/ops-crew.md](../recipes/ops-crew.md) |
| parallel-enricher | Parallel Calls | Skeleton | [recipes/parallel-enricher.md](../recipes/parallel-enricher.md) |
| memory-assistant | Memory | Skeleton | [recipes/memory-assistant.md](../recipes/memory-assistant.md) |
| hierarchical-agent | Multi-Agent (hierarchical) | Skeleton | [recipes/hierarchical-agent.md](../recipes/hierarchical-agent.md) |

---

## Worked example

> **Task:** "Build a Q&A bot that answers questions from our internal docs."

**Step 1 -- Define:**
- Agent answers natural-language questions using a corpus of documents.
- Input: user question (string). Output: answer + citations.
- External systems: document store, vector DB for retrieval.
- Latency: real-time (< 5s).

**Step 2 -- Pattern:** This is textbook RAG. Load [patterns/rag.md](../patterns/rag.md).

**Step 3 -- Framework:** We want Python, structured outputs for citations, and the agent is simple (no complex graph). Pydantic AI fits well. Load [frameworks/pydantic-ai.md](../frameworks/pydantic-ai.md). (LangGraph would also work if we wanted checkpointing.)

**Step 4 -- Stack:** Need vector DB (Qdrant), relational store (Postgres for doc metadata), cache (Redis), tracing (Langfuse), API (FastAPI). Load the relevant stack docs.

**Step 5 -- Cross-cutting:** All five apply. Load them.

**Step 6 -- Recipe:** `docs-rag-qa` is an exact match. Load [recipes/docs-rag-qa.md](../recipes/docs-rag-qa.md) and use it as the starting point.

**Total context loaded:** playbook + 1 pattern + 1 framework + 5 stack + 5 cross-cutting + 1 recipe = 14 small files. Ready to generate a coherent design and scaffold code.
