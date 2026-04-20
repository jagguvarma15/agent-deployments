# agent-deployments

Production-shaped AI agent prototypes with opinionated stack picks. Fork-ready starting points — not abstract patterns.

> **Companion to [`agent-blueprints`](https://github.com/jagguvarma15/agent-blueprints).**
> Where `agent-blueprints` teaches you *how to think about* agent systems,
> `agent-deployments` gives you **real, runnable prototypes** with **specific
> tool/framework picks** — clone, fill in env vars, `make up`, and you have a
> production-shaped agent running locally in under 5 minutes.

---

## Which prototype should I start from?

| If you're building... | Start here | Pattern |
|----------------------|------------|---------|
| A chatbot that routes to specialists | [`customer-support-triage`](prototypes/customer-support-triage/) | Routing + Tool Use |
| Q&A over your own docs | [`docs-rag-qa`](prototypes/docs-rag-qa/) | RAG |
| An open-ended research tool | [`research-assistant`](prototypes/research-assistant/) | ReAct + Tool Use |
| A content generation pipeline | [`content-pipeline`](prototypes/content-pipeline/) | Prompt Chaining + Evaluator-Optimizer |
| Automated code review | [`code-review-agent`](prototypes/code-review-agent/) | Plan & Execute + Reflection |
| A team of agents collaborating | [`ops-crew`](prototypes/ops-crew/) | Multi-Agent (flat) |
| Batch enrichment at scale | [`parallel-enricher`](prototypes/parallel-enricher/) | Parallel Calls |
| A personal assistant with memory | [`memory-assistant`](prototypes/memory-assistant/) | Memory |
| A hierarchical multi-agent system | [`hierarchical-agent`](prototypes/hierarchical-agent/) | Multi-Agent (hierarchical) |

Every prototype ships in **Python** and **TypeScript** side by side. Same architecture, different realization.

---

## The prototypes

| # | Prototype | Pattern(s) | Python framework | TypeScript framework |
|---|-----------|------------|------------------|---------------------|
| 1 | `customer-support-triage` | Routing + Tool Use | Pydantic AI | Mastra |
| 2 | `docs-rag-qa` | RAG | LangGraph | Mastra |
| 3 | `research-assistant` | ReAct + Tool Use | LangGraph | Mastra |
| 4 | `content-pipeline` | Prompt Chaining + Evaluator-Optimizer | Pydantic AI | Vercel AI SDK + Mastra |
| 5 | `code-review-agent` | Plan & Execute + Reflection | LangGraph | Mastra |
| 6 | `ops-crew` | Multi-Agent (flat) | CrewAI | Mastra |
| 7 | `parallel-enricher` | Parallel Calls | Pydantic AI + asyncio | Mastra workflows |
| 8 | `memory-assistant` | Memory | LangGraph + mem0 | Mastra + mem0 |
| 9 | `hierarchical-agent` | Multi-Agent (hierarchical) | LangGraph Supervisor | Mastra |

---

## What "production-shaped" means

Every prototype implements the same **11-point checklist**:

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
11. **Docs** — README, architecture diagram, swap guide, eval docs

---

## The canonical stack

One opinionated pick per slot. No "it depends." See [`docs/stack.md`](docs/stack.md) for the full table with rationale.

| Slot | Pick |
|------|------|
| LLM (primary) | Anthropic Claude (Sonnet 4.6 / Haiku 4.5) |
| Agent framework (Py) | LangGraph, Pydantic AI, or CrewAI (per prototype) |
| Agent framework (TS) | Mastra (+ Vercel AI SDK where noted) |
| API layer | FastAPI (Py) / Hono (TS) |
| Vector DB | Qdrant (self-hosted) |
| Relational store | Postgres 16 |
| Cache / rate limit | Redis 7 |
| Observability | Langfuse (self-hosted) |
| Eval | DeepEval + RAGAS + Promptfoo |
| Tool protocol | MCP (Model Context Protocol) |
| Container orchestration | docker-compose |

Want to swap a pick? Each prototype has a [`docs/swaps.md`](docs/stack.md) documenting alternatives.

---

## Quick start

```bash
# Pick a prototype
cd prototypes/customer-support-triage/python  # or typescript

# Configure
cp .env.example .env
# Add your ANTHROPIC_API_KEY (and any other keys) to .env

# Run
make up

# Verify
curl http://localhost:8000/health
```

See [`docs/quickstart.md`](docs/quickstart.md) for the full walkthrough.

---

## Repo structure

```
agent-deployments/
├── docs/                           # Stack docs, deployment guides, eval philosophy
├── common/                         # Shared libraries (auth, logging, tracing, MCP)
│   ├── python/
│   ├── typescript/
│   ├── docker/
│   └── docker-compose.base.yml
├── prototypes/
│   ├── customer-support-triage/
│   ├── docs-rag-qa/
│   ├── research-assistant/
│   ├── content-pipeline/
│   ├── code-review-agent/
│   ├── ops-crew/
│   ├── parallel-enricher/
│   ├── memory-assistant/
│   └── hierarchical-agent/
└── Makefile
```

Each prototype:
```
prototypes/<name>/
├── README.md           # Shared: problem, design, blueprint map
├── ARCHITECTURE.md     # Mermaid diagrams, data flow
├── python/             # Python implementation
├── typescript/         # TypeScript implementation
└── docs/               # Swaps, eval docs
```

---

## Relationship to agent-blueprints

```
agent-blueprints          →    agent-deployments
(architecture)                 (execution)

pattern: ReAct             →    prototype: research-assistant
                                (LangGraph + Tavily + FastAPI + Langfuse)
```

Each prototype's README opens with a **Blueprint Map** linking back to the relevant pattern pages. See [`docs/blueprint-map.md`](docs/blueprint-map.md) for the full mapping.

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for how to add a prototype or submit a stack swap.

## License

[MIT](LICENSE)
