# Quickstart

Build an agent from a blueprint using AI-assisted development. Start minimal, add production concerns when you're ready.

## Prerequisites

- An **AI coding assistant** (Claude Code, Cursor, etc.) to use the blueprints as context
- **API keys**: at minimum, `ANTHROPIC_API_KEY`

For local development:
- **Python track**: Python 3.12+, [uv](https://docs.astral.sh/uv/)
- **TypeScript track**: Node 22 LTS, [pnpm](https://pnpm.io/)

For containerized deployment:
- **Docker** and **Docker Compose** (v2)

## The three tiers

Not every agent needs every component on day one. Build incrementally:

| Tier | What you get | Docs to load | Time |
|------|-------------|--------------|------|
| **1. Working agent** | Core agent logic running locally | Recipe + pattern + framework | Quick start |
| **2. API-ready** | Containerized with API, DB, Docker | + stack docs + reference templates | Add when serving |
| **3. Production-shaped** | Auth, rate limiting, observability, CI, eval | + cross-cutting docs | Add before shipping |

Each recipe's **Load as Context** section tells you exactly which files to load for each tier.

---

## Tier 1: Working agent

Get the core agent running locally — no Docker, no infrastructure.

### 1. Pick a blueprint

Browse [`docs/recipes/`](recipes/) and choose a blueprint. Each recipe's **Load as Context** section lists the minimum docs to load.

### 2. Load core docs as AI context

Feed these to your AI coding assistant:

```
docs/recipes/<your-recipe>.md        # The full blueprint
docs/patterns/<pattern>.md            # The underlying architecture
docs/frameworks/<framework>.md        # Idiomatic implementation guide
docs/stack/llm-claude.md              # LLM integration
```

### 3. Prompt your AI assistant

Use this template (copy-paste and fill in):

```
You are building an AI agent from a blueprint specification. I'm giving you
a set of markdown docs that fully specify the agent.

Your job:
1. Read the blueprint recipe — it has the data models, prompts, tool specs,
   and implementation roadmap.
2. Use the pattern doc to understand the architecture and data flow.
3. Use the framework doc for idiomatic code patterns.
4. Build the agent core: data models, tools, prompts, and the main agent loop.

Target: Tier 1 (working agent). Skip API layer, auth, rate limiting,
Docker, and observability for now. Just get the agent running locally
with a simple script entry point.

Language: [Python / TypeScript]
Framework: [Pydantic AI / LangGraph / CrewAI / Vercel AI SDK / Mastra]

Here are the docs:
[paste or attach the files listed above]
```

### 4. Run it

```bash
# Python
uv run python -m app.main

# TypeScript
pnpm tsx src/index.ts
```

---

## Tier 2: API-ready

Wrap your agent in an API, add a database, and containerize it.

### Additional docs to load

```
docs/stack/api-fastapi.md             # or api-hono.md for TypeScript
docs/stack/relational-postgres.md     # if your recipe needs it (check dependency table)
docs/stack/cache-redis.md             # if your recipe needs it
docs/reference/docker-templates.md    # Dockerfile templates
docs/reference/docker-compose-template.md  # Infrastructure stack
```

### What to tell your AI assistant

```
Now upgrade to Tier 2. Using the stack docs and reference templates:
1. Add the API layer (FastAPI/Hono) with the endpoints from the API Contract section.
2. Add Postgres for persistence (if needed per the dependency table).
3. Create a Dockerfile and docker-compose.yml from the reference templates.
4. Add a .env.example with the vars from the Environment & Deployment section.
```

### Run it

```bash
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

docker compose up

# Verify
curl http://localhost:8000/health
```

---

## Tier 3: Production-shaped

Add security, observability, testing, and CI.

### Additional docs to load

```
docs/cross-cutting/auth-jwt.md        # JWT endpoint protection
docs/cross-cutting/rate-limiting.md   # Per-user throttling
docs/cross-cutting/logging-structured.md   # JSON logging
docs/cross-cutting/observability.md   # Langfuse tracing
docs/cross-cutting/testing-strategy.md     # Unit / integration / eval tiers
docs/stack/tracing-langfuse.md        # Langfuse setup
docs/stack/eval-deepeval-ragas-promptfoo.md  # Eval tooling
docs/reference/ci-template.md         # GitHub Actions workflow
```

### What to tell your AI assistant

```
Now upgrade to Tier 3 (production-shaped). Using the cross-cutting docs:
1. Add JWT auth middleware to all agent endpoints.
2. Add Redis-backed rate limiting.
3. Add structured JSON logging with request context.
4. Add Langfuse tracing on all LLM and tool calls.
5. Write tests following the Test Strategy section (unit with mocked LLM, integration, eval).
6. Set up CI from the CI template.
```

### Verify

Open http://localhost:3000 to see Langfuse traces for your requests.

---

## Swapping stack components

Don't want Qdrant? Prefer OpenAI over Claude? See [`docs/playbook/stack-swaps.md`](playbook/stack-swaps.md) for a complete swap guide covering every slot in the stack.

---

## Composing patterns

Many agents combine multiple patterns. For example, a research assistant might use ReAct for its core loop but RAG for document retrieval in one of its tools. When composing:

1. Pick the **primary** blueprint (the one closest to your use case)
2. Load the **secondary** pattern doc for the pattern you're mixing in
3. Check the blueprint map at [`docs/blueprint-map.md`](blueprint-map.md) for which blueprints share patterns

Common compositions:
- **ReAct + RAG**: Load `research-assistant` recipe + `patterns/rag.md` for a research agent with document retrieval
- **Routing + Memory**: Load `customer-support-triage` recipe + `patterns/memory.md` for a support agent that remembers past conversations
- **Plan-Execute + Parallel**: Load `code-review-agent` recipe + `patterns/parallel-calls.md` for file-level parallel analysis

---

## Troubleshooting

- **Port conflicts**: Default ports are 8000 (API), 5432 (Postgres), 6379 (Redis), 6333 (Qdrant), 3000 (Langfuse). Check with `lsof -i :<port>`.
- **Docker memory**: Langfuse + Qdrant + Postgres can use 2-4 GB. Ensure Docker has enough memory allocated.
- **Missing env vars**: The app validates config at boot. If a required var is missing, you'll see a clear error message.
- **Which tier am I on?** Check your recipe's dependency table — if a "Required" component is missing, you'll hit errors at that tier.

## Next steps

- Read the blueprint's **Design Decisions** section to understand trade-offs
- Use the **Eval Dataset** section to verify your implementation against golden examples
- See [`docs/playbook/production-checklist.md`](playbook/production-checklist.md) for the full 11-point readiness gate
- See [`docs/playbook/stack-swaps.md`](playbook/stack-swaps.md) to swap any component for an alternative
