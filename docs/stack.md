# The Canonical Production Stack

One opinionated pick per slot. Every prototype uses these defaults unless its
README explicitly overrides with a rationale.

## Stack table

| Slot | Pick | Why this pick |
|------|------|---------------|
| **LLM provider (primary)** | Anthropic Claude (Sonnet 4.6 default, Haiku 4.5 for cheap/fast paths) | Strong tool use, MCP-native, long context. `litellm` / `ai` SDK abstract the swap. |
| **LLM provider (alt)** | OpenAI GPT-4.1 / 5 via `litellm` (Py) or Vercel AI SDK providers (TS) | One-line swap for benchmarking. |
| **Agent framework (Py, stateful)** | **LangGraph** | Checkpointing, LangSmith integration, production-proven. |
| **Agent framework (Py, structured)** | **Pydantic AI** | Type-safe outputs, clean DX, great for routing/classifier prototypes. |
| **Agent framework (Py, multi-agent crew)** | **CrewAI** | Role/goal/backstory abstraction is faster for the "crew" mental model. |
| **Agent framework (TS, all)** | **Mastra** (+ Vercel AI SDK for web-facing variants) | TS-native, batteries-included, v1, built on AI SDK. |
| **API layer (Py)** | **FastAPI + Uvicorn** (behind Gunicorn for prod) | De-facto Python agent-serving pattern; auto OpenAPI docs; async-native. |
| **API layer (TS)** | **Hono** (Node runtime; Cloudflare Workers-compatible) | Minimal, fast, works on edge or Node; pairs cleanly with Mastra. |
| **Vector DB (default)** | **Qdrant** (self-hosted via Docker) | Best latency/filtering for self-hosted; MIT-licensed; strong Py + TS clients. |
| **Vector DB (alt)** | **pgvector** on Postgres (when Postgres is already present) | Zero new infra; fine up to ~5M vectors. |
| **Relational store** | **Postgres 16** | LangGraph checkpointer, app state, Alembic migrations. |
| **Cache / rate limit / session** | **Redis 7** (or Valkey) | `slowapi` (Py) / Hono rate-limit middleware (TS) back-end. |
| **Observability / tracing** | **Langfuse** (self-hosted, MIT) | Open-source, framework-agnostic, OpenTelemetry-compatible. LangSmith as opt-in for LangGraph prototypes. |
| **Eval — prompt/unit** | **DeepEval** (Python, pytest-native, 50+ metrics, agent-trace-aware) | Runs in CI; dedicated agent metrics. |
| **Eval — RAG-specific** | **RAGAS** (for the `docs-rag-qa` prototype) | Purpose-built RAG metrics (faithfulness, answer relevancy, context recall). |
| **Eval — red-team / security** | **Promptfoo** | YAML-configured scans for jailbreaks, prompt injection, PII leakage; runs in CI. |
| **Memory (long-term)** | **mem0** backed by Postgres + pgvector | Battle-tested facts + semantic memory layer; Py and TS SDKs. |
| **Web search tool** | **Tavily** (primary) with **Exa** alt | Both have clean Py/TS SDKs and agent-shaped APIs. |
| **Tool protocol** | **MCP (Model Context Protocol)** | Linux Foundation standard. Tools as MCP servers work across frameworks. |
| **Auth** | **JWT** (HS256 for local, RS256 for prod hint) via `fastapi-users` / `hono/jwt` | Standard, portable. |
| **Rate limiting** | `slowapi` (Py) / `hono-rate-limiter` (TS), Redis-backed | Per-user and per-endpoint. |
| **Structured logging** | `structlog` (Py) / `pino` (TS), JSON output | Request / session / user context on every line. |
| **Migrations** | `alembic` (Py) / `drizzle-kit` (TS) | Schema-as-code. |
| **Container** | Multi-stage Docker (slim base, <200 MB target) | One `Dockerfile` per track. |
| **Local orchestration** | **docker-compose** | One file per prototype: API + Postgres + Redis + Qdrant + Langfuse. |
| **Cloud deployment hints** | **AWS Fargate** and **Google Cloud Run** | No IaC in v1; pointers + Dockerfile-compatibility notes in `docs/deploy/`. |
| **CI** | **GitHub Actions** | lint, typecheck, unit, eval, docker build, security scan. |
| **Package manager (Py)** | **uv** | Fastest, reproducible lockfiles. |
| **Package manager (TS)** | **pnpm** | Workspace-friendly for the monorepo. |
| **Linter/formatter (Py)** | **ruff** | Replaces black + flake8 + isort. |
| **Linter/formatter (TS)** | **Biome** | Replaces eslint + prettier. |

## Swap documentation

Each prototype's `docs/swaps.md` categorizes alternatives:

- **Single-file swap** — e.g., change the `litellm` model string to switch LLM providers
- **Multi-file swap** — e.g., Qdrant to Pinecone affects the indexer, retriever, and docker-compose
- **Architectural swap** — e.g., LangGraph to OpenAI Agents SDK requires rethinking the state model

## Why these picks over the obvious alternatives

- **LangGraph over AutoGen/AG2** — Better observability, better state model, MCP integration quality.
- **Mastra over pure Vercel AI SDK** — AI SDK is the engine; Mastra is the assembled car with memory, workflows, and eval built in.
- **Qdrant over Pinecone** — Self-hostable, MIT, better p99 latency in benchmarks, no vendor lock-in for offline `make up`.
- **Langfuse over LangSmith** — Framework-agnostic, self-hostable, MIT. LangSmith is the swap for LangChain-heavy teams.
- **MCP over framework-native tools** — The protocol is the standard; tools built as MCP servers work across all frameworks.
- **CrewAI for `ops-crew` only** — One CrewAI prototype lets readers see the role-based abstraction; the TS implementation using Mastra makes the contrast concrete.
- **DeepEval + RAGAS + Promptfoo (three tools)** — Genuinely different surfaces: general evals, RAG metrics, and red-team/security.
