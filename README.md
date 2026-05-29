# agent-deployments

Composable agent blueprints for production AI deployments. Everything you need to build, test, and deploy AI agents — as self-contained markdown specs.

---

## The three-repo ecosystem

This repo is one of three that work together as a single pipeline:

```
agent-blueprints     →     agent-deployments    →     agent-scaffold
(architecture)             (specs)                    (generator)
"how to think"             "what to build"            "build it for me"
patterns + tradeoffs       9 production-shaped        reads spec, asks LLM,
framework-agnostic         markdown blueprints        writes runnable project
```

- **[agent-blueprints](https://github.com/jagguvarma15/agent-blueprints)** — framework-agnostic patterns, tradeoffs, and design guidance. Start here if you want to design before you build.
- **[agent-deployments](https://github.com/jagguvarma15/agent-deployments)** *(this repo)* — opinionated, production-shaped markdown specs for nine concrete agents (Python + TypeScript tracks).
- **[agent-scaffold](https://github.com/jagguvarma15/agent-scaffold)** — a CLI that consumes a deployment spec, asks Claude to emit a complete project, and writes the files atomically to disk.

If you want to skip the manual "load these docs into your AI assistant" step in the Quick Start below, point `agent-scaffold` at this repo and it'll do the assembly + generation for you.

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
2. **Check its "Load as Context" section** — it lists the exact files to feed your AI coding assistant, split by tier
3. **Start at Tier 1** (working agent) — just the recipe + pattern + framework docs. No Docker, no infra.
4. **Add Tier 2** (API-ready) when you need to serve it — API layer, DB, Docker
5. **Add Tier 3** (production) when you're shipping — auth, rate limiting, observability, CI

Each recipe also has an **Infrastructure Dependencies** table showing what's required vs optional. See [`docs/quickstart.md`](docs/quickstart.md) for the full walkthrough with AI prompt templates.

Want to swap a stack component? See [`docs/playbook/stack-swaps.md`](docs/playbook/stack-swaps.md).

---

## Repo structure

```
agent-deployments/
├── docs/
│   ├── recipes/           # 9 agent blueprints (the main content)
│   ├── patterns/          # 9 agent design patterns
│   ├── frameworks/        # Framework-specific guides (LangGraph, Pydantic AI, etc.)
│   ├── stack/             # Stack choice docs (Postgres, Redis, Qdrant, etc.)
│   ├── capabilities/      # Provisioning contracts consumed by agent-scaffold up
│   ├── cross-cutting/     # Auth, logging, observability, rate limiting, testing
│   ├── reference/         # Dockerfile, docker-compose, CI, Makefile templates
│   └── playbook/          # Design guides and production checklist
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
└── LICENSE
```

---

## Capabilities

`agent-scaffold` (≥ v0.3) doesn't just generate code anymore — it provisions the local stack and emits cloud-deploy configs. The unit of provisioning is a **capability**: a high-level infra need with everything needed to stand it up.

```yaml
# In a recipe's frontmatter:
capabilities:
  - cache.redis
  - relational.postgres
  - vector_db.qdrant
  - queue.kafka
  - obs.langsmith
  - frontend.nextjs-chat
  - host.vercel
```

`agent-scaffold` resolves each id against [`docs/capabilities/`](docs/capabilities/), feeds the capability bodies to the LLM during generation, then runs per-capability bootstrap steps after `docker compose up` (create vector collections, create Kafka topics, create LangSmith project, provision Grafana datasources, write `vercel.json`, etc.).

See [`docs/capabilities/README.md`](docs/capabilities/README.md) for the catalog, frontmatter schema, and authoring guide. Older `agent-scaffold` versions ignore the `capabilities:` field — recipes stay backwards-compatible.

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
