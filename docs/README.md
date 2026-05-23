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
| [stack-swaps.md](playbook/stack-swaps.md) | How to swap any stack component for an alternative |

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
| [event-driven.md](patterns/event-driven.md) | Event-Driven Agents (queue/stream triggered) |

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
| [secrets-management.md](stack/secrets-management.md) | Secrets storage (dev `.env` → prod Vault / cloud secret manager) |
| [opentelemetry.md](stack/opentelemetry.md) | OTel SDK + Collector for distributed tracing across services |
| [prometheus-grafana.md](stack/prometheus-grafana.md) | Metrics scraping + dashboards + alerting + SLO tracking |
| [log-aggregation.md](stack/log-aggregation.md) | Centralized log search (Loki + Promtail, or managed alternatives) |
| [kafka.md](stack/kafka.md) | Kafka 3.x (KRaft) for >10k events/sec, durable replay, cross-team fan-out |
| [kubernetes-helm.md](stack/kubernetes-helm.md) | Managed K8s + Helm chart structure; HPA / KEDA; ExternalSecret; NetworkPolicy |
| [terraform.md](stack/terraform.md) | OpenTofu / Terraform; module structure; remote state with locking; plan/apply CI |

## Cross-cutting

One file per shared concern. Answers: "What production plumbing do I need?"

| Doc | Concern |
|-----|---------|
| [auth-jwt.md](cross-cutting/auth-jwt.md) | JWT authentication |
| [logging-structured.md](cross-cutting/logging-structured.md) | Structured JSON logging |
| [observability.md](cross-cutting/observability.md) | Langfuse tracing integration |
| [rate-limiting.md](cross-cutting/rate-limiting.md) | Per-user / per-IP rate limiting |
| [testing-strategy.md](cross-cutting/testing-strategy.md) | 3-tier test strategy (unit / integration / eval) |
| [schema-evolution.md](cross-cutting/schema-evolution.md) | Versioning events without breaking consumers (`schema_version`, dual-publish) |
| [validation-strategy.md](cross-cutting/validation-strategy.md) | Boundary validation with Pydantic v2 / Zod; LLM output validation; error-response shape |
| [caching-strategies.md](cross-cutting/caching-strategies.md) | Cache-aside, TTL + jitter, singleflight, LLM response caching, negative caching |
| [multi-tenancy.md](cross-cutting/multi-tenancy.md) | Three isolation models, Postgres RLS, tenant propagation, per-tenant rate limits |
| [idempotency.md](cross-cutting/idempotency.md) | At-least-once-safe action handlers (two-phase claim, SETNX, unique constraints, outbound keys) |
| [resilience.md](cross-cutting/resilience.md) | Retries, timeouts, circuit breakers, bulkheads |
| [health-graceful-shutdown.md](cross-cutting/health-graceful-shutdown.md) | Startup / liveness / readiness probes + SIGTERM drain sequence |
| [distributed-locking.md](cross-cutting/distributed-locking.md) | Single-leader mutual exclusion (Redis + Lua, Postgres advisory) |
| [security-hardening.md](cross-cutting/security-hardening.md) | OWASP for agents, prompt injection, deps, TLS / mTLS, container hardening |
| [authorization-rbac.md](cross-cutting/authorization-rbac.md) | RBAC / ABAC / PBAC; per-intent tool allowlists; tenant-scoped checks |
| [audit-logging.md](cross-cutting/audit-logging.md) | Immutable audit trail (Postgres + hash chain + S3 archive) |
| [pii-gdpr.md](cross-cutting/pii-gdpr.md) | PII storage, right-to-erasure, LLM redaction, DLP screens |

## Recipes

Full-spec agent blueprints. Answers: "Give me everything I need to build this agent." Each recipe includes a **Load as Context** section listing exactly which files to feed your AI assistant, and an **Infrastructure Dependencies** table showing what's required vs optional.

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
| [restaurant-rebooking.md](recipes/restaurant-rebooking.md) | Event-Driven + Multi-Agent Flat | Blueprint (design spec) |

## Reference

| Doc | Description |
|-----|-------------|
| [reference/](reference/) | Dockerfile, docker-compose, CI, and Makefile templates for project scaffolding |
