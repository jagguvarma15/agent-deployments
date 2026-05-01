# agent-deployments

Composable agent blueprints for production AI deployments. Everything you need to build, test, and deploy AI agents — as self-contained markdown specs.

> **Companion to [`agent-blueprints`](https://github.com/jagguvarma15/agent-blueprints).**
> Where `agent-blueprints` teaches you *how to think about* agent systems,
> `agent-deployments` gives you **complete implementation specs** with **specific
> stack picks** — load the relevant docs as AI context, and build a
> production-shaped agent from the blueprint.

---

## Which blueprint should I start from?

| If you're building... | Start here | Pattern |
|----------------------|------------|---------|
| A chatbot that routes to specialists | [`customer-support-triage`](docs/recipes/customer-support-triage.md) | Routing + Tool Use |
| Q&A over your own docs | [`docs-rag-qa`](docs/recipes/docs-rag-qa.md) | RAG |
| An open-ended research tool | [`research-assistant`](docs/recipes/research-assistant.md) | ReAct + Tool Use |
| A content generation pipeline | [`content-pipeline`](docs/recipes/content-pipeline.md) | Prompt Chaining |
| Automated code review | [`code-review-agent`](docs/recipes/code-review-agent.md) | Plan, Execute, Reflect |
| A team of agents collaborating | [`ops-crew`](docs/recipes/ops-crew.md) | Multi-Agent (flat) |
| Batch enrichment at scale | [`parallel-enricher`](docs/recipes/parallel-enricher.md) | Parallel Calls |
| A personal assistant with memory | [`memory-assistant`](docs/recipes/memory-assistant.md) | Memory |
| A hierarchical multi-agent system | [`hierarchical-agent`](docs/recipes/hierarchical-agent.md) | Multi-Agent (hierarchical) |

Every blueprint includes **Python** (FastAPI + Pydantic AI) and **TypeScript** (Hono + Vercel AI SDK) specifications side by side.

---

## What's in a blueprint?

Each blueprint is a full-spec markdown document with 13 sections:

1. **What it does** — problem statement and approach
2. **Architecture** — ASCII diagram of the agent flow
3. **Data Models** — full Pydantic + Zod schemas with field docs
4. **API Contract** — every endpoint with request/response JSON and error codes
5. **Tool Specifications** — each tool with parameters, return types, examples
6. **Prompt Specifications** — actual system prompts with design rationale
7. **Key files** — file-by-file implementation spec (Python + TypeScript)
8. **Implementation Roadmap** — ordered build steps
9. **Environment & Deployment** — env vars table, Docker Compose reference
10. **Test Strategy** — example tests per tier (unit/integration/eval)
11. **Eval Dataset** — inline golden examples
12. **Design Decisions** — trade-offs and rationale
13. **Reference Implementation** — full source code (validated blueprints only)

---

## What "production-shaped" means

Every blueprint specifies the same **11-point checklist**:

1. **Containerized** — multi-stage Dockerfile, <200 MB final image
2. **Local up in one command** — `docker compose up` brings everything online
3. **Config via env** — `.env.example` committed, validated at boot
4. **Auth** — JWT-bearer on all agent endpoints
5. **Rate limiting** — per-user and per-IP, Redis-backed
6. **Structured logging** — JSON with request/session/user context
7. **Tracing** — every LLM call, tool call, and agent step traced in Langfuse
8. **Persistence** — conversation state in Postgres with managed migrations
9. **Tests** — unit (mocked LLM), integration (real LLM), eval (golden datasets)
10. **CI** — lint, typecheck, unit, eval, docker build, security scan
11. **Docs** — architecture diagram, API contract, eval docs

---

## The canonical stack

One opinionated pick per slot. See [`docs/stack/`](docs/stack/) for detailed rationale per choice.

| Slot | Pick |
|------|------|
| LLM (primary) | Anthropic Claude (Sonnet 4.6 / Haiku 4.5) |
| Agent framework (Py) | LangGraph, Pydantic AI, or CrewAI (per blueprint) |
| Agent framework (TS) | Vercel AI SDK |
| API layer | FastAPI (Py) / Hono (TS) |
| Vector DB | Qdrant (self-hosted) |
| Relational store | Postgres 16 |
| Cache / rate limit | Redis 7 |
| Observability | Langfuse (self-hosted) |
| Eval | DeepEval + RAGAS + Promptfoo |
| Tool protocol | MCP (Model Context Protocol) |
| Container orchestration | docker-compose |

---

## Quick start

1. **Pick a blueprint** from the table above
2. **Load the docs** — feed the blueprint + relevant [cross-cutting](docs/cross-cutting/) and [stack](docs/stack/) docs as context to your AI coding assistant
3. **Scaffold** — use the [reference templates](docs/reference/) (Dockerfile, docker-compose, CI) to set up your project
4. **Build** — follow the Implementation Roadmap in the blueprint
5. **Test** — use the Test Strategy and Eval Dataset sections

See [`docs/quickstart.md`](docs/quickstart.md) for the full walkthrough.

---

## Repo structure

```
agent-deployments/
├── docs/
│   ├── recipes/           # 9 agent blueprints (the main content)
│   ├── patterns/          # 9 agent design patterns
│   ├── frameworks/        # Framework-specific guides (LangGraph, Pydantic AI, etc.)
│   ├── stack/             # Stack choice docs (Postgres, Redis, Qdrant, etc.)
│   ├── cross-cutting/     # Auth, logging, observability, rate limiting, testing
│   ├── reference/         # Dockerfile, docker-compose, CI, Makefile templates
│   └── playbook/          # Design guides and production checklist
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
└── LICENSE
```

---

## Relationship to agent-blueprints

```
agent-blueprints          →    agent-deployments
(architecture)                 (execution)

pattern: ReAct             →    blueprint: research-assistant
                                (Pydantic AI + FastAPI + Langfuse + full spec)
```

Each blueprint opens with a **Composes** section linking to the relevant pattern, framework, and stack docs. See [`docs/blueprint-map.md`](docs/blueprint-map.md) for the full mapping.

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for how to contribute a blueprint or improve existing docs.

## License

[MIT](LICENSE)
