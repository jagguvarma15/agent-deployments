# Quickstart

Build an agent from a blueprint using AI-assisted development.

## Prerequisites

- An **AI coding assistant** (Claude Code, Cursor, etc.) to use the blueprints as context
- **Docker** and **Docker Compose** (v2) for running infrastructure
- **API keys**: at minimum, `ANTHROPIC_API_KEY`

For local development:
- **Python track**: Python 3.12+, [uv](https://docs.astral.sh/uv/)
- **TypeScript track**: Node 22 LTS, [pnpm](https://pnpm.io/)

## Steps

### 1. Clone

```bash
git clone https://github.com/jagguvarma15/agent-deployments.git
cd agent-deployments
```

### 2. Pick a blueprint

Browse [`docs/recipes/`](recipes/) and choose a blueprint that matches your use case. Each recipe doc is self-contained — it includes architecture, data models, API contracts, prompts, and implementation roadmap.

### 3. Load docs as AI context

Feed the blueprint and its referenced docs to your AI coding assistant:

```
# Core blueprint
docs/recipes/customer-support-triage.md

# Referenced cross-cutting concerns
docs/cross-cutting/auth-jwt.md
docs/cross-cutting/logging-structured.md
docs/cross-cutting/observability.md
docs/cross-cutting/rate-limiting.md

# Referenced stack docs
docs/stack/api-fastapi.md        # or api-hono.md for TypeScript
docs/stack/relational-postgres.md
docs/stack/cache-redis.md
docs/stack/tracing-langfuse.md

# Project scaffolding templates
docs/reference/docker-templates.md
docs/reference/docker-compose-template.md
```

### 4. Scaffold the project

Use the [reference templates](reference/) to set up your project structure:

- **Dockerfile**: See [`docs/reference/docker-templates.md`](reference/docker-templates.md) for multi-stage Python and TypeScript Dockerfiles
- **docker-compose.yml**: See [`docs/reference/docker-compose-template.md`](reference/docker-compose-template.md) for the base infrastructure stack
- **CI pipeline**: See [`docs/reference/ci-template.md`](reference/ci-template.md) for GitHub Actions workflow

### 5. Build following the roadmap

Each blueprint has an **Implementation Roadmap** section with ordered build steps. Follow them sequentially — each step builds on the previous one.

### 6. Configure and run

```bash
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

docker compose up

# Verify
curl http://localhost:8000/health
```

### 7. View traces

Open http://localhost:3000 to see Langfuse traces for your requests.

## Troubleshooting

- **Port conflicts**: Default ports are 8000 (API), 5432 (Postgres), 6379 (Redis), 6333 (Qdrant), 3000 (Langfuse). Check for conflicts with `lsof -i :<port>`.
- **Docker memory**: Langfuse + Qdrant + Postgres can use 2-4 GB. Ensure Docker has enough memory allocated.
- **Missing env vars**: The app validates config at boot. If a required var is missing, you'll see a clear error message.

## Next steps

- Read the blueprint's **Design Decisions** section to understand trade-offs
- Check [`docs/stack/`](stack/) for the full stack rationale
- Use the **Test Strategy** and **Eval Dataset** sections to verify your implementation
- See [`docs/playbook/production-checklist.md`](playbook/production-checklist.md) for deployment readiness
