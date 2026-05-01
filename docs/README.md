# agent-deployments / docs

Composable markdown context for designing, building, and deploying AI agents.

Load the small docs you need for your design — one file per axis of choice.

## How to use these docs

1. Start with the **playbook** to walk the design process.
2. Pick a **pattern** that matches your problem shape.
3. Pick a **framework** that fits the pattern and your language.
4. Pick **stack** components for infra (DB, cache, tracing, etc.).
5. Apply **cross-cutting** concerns (auth, logging, rate limiting).
6. Reference the closest **recipe** for a worked example.

For AI-assisted design: load the playbook + the relevant pattern + framework + stack docs as context. Total: ~12 small files, zero source code needed for the design pass.

---

## Playbook

| Doc | Description |
|-----|-------------|
| [design-a-new-agent.md](playbook/design-a-new-agent.md) | Step-by-step workflow: pattern, framework, stack, compose |
| [production-checklist.md](playbook/production-checklist.md) | The 11-point checklist every blueprint specifies |

## Patterns

One file per architecture pattern. Answers: "What shape does my agent take?"

| Doc | Pattern |
|-----|---------|
| [rag.md](patterns/rag.md) | Retrieval-Augmented Generation |
| [react.md](patterns/react.md) | ReAct (Reason + Act) loop |
| [routing-tool-use.md](patterns/routing-tool-use.md) | Intent routing + tool dispatch |
| [prompt-chaining.md](patterns/prompt-chaining.md) | Sequential prompt pipeline |
| [plan-execute-reflect.md](patterns/plan-execute-reflect.md) | Plan, execute steps, reflect |
| [parallel-calls.md](patterns/parallel-calls.md) | Fan-out / fan-in parallel execution |
| [memory.md](patterns/memory.md) | Long-term memory across sessions |
| [multi-agent-flat.md](patterns/multi-agent-flat.md) | Peer agents collaborating |
| [multi-agent-hierarchical.md](patterns/multi-agent-hierarchical.md) | Supervisor delegates to sub-agents |

## Frameworks

One file per agent framework. Answers: "How do I implement the pattern?"

| Doc | Framework | Language |
|-----|-----------|----------|
| [langgraph.md](frameworks/langgraph.md) | LangGraph | Python |
| [pydantic-ai.md](frameworks/pydantic-ai.md) | Pydantic AI | Python |
| [crewai.md](frameworks/crewai.md) | CrewAI | Python |
| [mastra.md](frameworks/mastra.md) | Mastra | TypeScript |
| [vercel-ai-sdk.md](frameworks/vercel-ai-sdk.md) | Vercel AI SDK | TypeScript |

## Stack

One file per infrastructure component. Answers: "What do I run it on?"

| Doc | Component |
|-----|-----------|
| [llm-claude.md](stack/llm-claude.md) | Anthropic Claude (primary LLM) |
| [api-fastapi.md](stack/api-fastapi.md) | FastAPI + Uvicorn (Python API) |
| [api-hono.md](stack/api-hono.md) | Hono (TypeScript API) |
| [vector-qdrant.md](stack/vector-qdrant.md) | Qdrant (vector DB) |
| [relational-postgres.md](stack/relational-postgres.md) | Postgres 16 (relational store) |
| [cache-redis.md](stack/cache-redis.md) | Redis 7 (cache + rate limiting) |
| [tracing-langfuse.md](stack/tracing-langfuse.md) | Langfuse (observability) |
| [eval-deepeval-ragas-promptfoo.md](stack/eval-deepeval-ragas-promptfoo.md) | DeepEval + RAGAS + Promptfoo (eval) |
| [tool-protocol-mcp.md](stack/tool-protocol-mcp.md) | MCP (Model Context Protocol) |

## Cross-cutting

One file per shared concern. Answers: "What production plumbing do I need?"

| Doc | Concern |
|-----|---------|
| [auth-jwt.md](cross-cutting/auth-jwt.md) | JWT authentication |
| [logging-structured.md](cross-cutting/logging-structured.md) | Structured JSON logging |
| [observability.md](cross-cutting/observability.md) | Langfuse tracing integration |
| [rate-limiting.md](cross-cutting/rate-limiting.md) | Per-user / per-IP rate limiting |
| [testing-strategy.md](cross-cutting/testing-strategy.md) | 3-tier test strategy (unit / integration / eval) |

## Recipes

Full-spec agent blueprints. Answers: "Give me everything I need to build this agent."

| Doc | Pattern | Status |
|-----|---------|--------|
| [customer-support-triage.md](recipes/customer-support-triage.md) | Routing + Tool Use | Blueprint (validated) |
| [docs-rag-qa.md](recipes/docs-rag-qa.md) | RAG pipeline | Blueprint (validated) |
| [research-assistant.md](recipes/research-assistant.md) | ReAct research agent | Blueprint (validated) |
| [content-pipeline.md](recipes/content-pipeline.md) | Prompt chaining pipeline | Blueprint (design spec) |
| [code-review-agent.md](recipes/code-review-agent.md) | Plan, Execute, Reflect | Blueprint (design spec) |
| [ops-crew.md](recipes/ops-crew.md) | Multi-agent ops crew | Blueprint (design spec) |
| [parallel-enricher.md](recipes/parallel-enricher.md) | Parallel batch enrichment | Blueprint (design spec) |
| [memory-assistant.md](recipes/memory-assistant.md) | Memory-enabled assistant | Blueprint (design spec) |
| [hierarchical-agent.md](recipes/hierarchical-agent.md) | Hierarchical multi-agent | Blueprint (design spec) |

## Reference

| Doc | Description |
|-----|-------------|
| [reference/](reference/) | Dockerfile, docker-compose, CI, and Makefile templates for project scaffolding |
