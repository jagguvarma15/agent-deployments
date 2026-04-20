# Quickstart

Get any prototype running locally in under 5 minutes.

## Prerequisites

- **Docker** and **Docker Compose** (v2)
- **API keys**: at minimum, `ANTHROPIC_API_KEY` — some prototypes need additional keys (Tavily, Cohere, etc.)

For local development without Docker:
- **Python track**: Python 3.12+, [uv](https://docs.astral.sh/uv/)
- **TypeScript track**: Node 22 LTS, [pnpm](https://pnpm.io/)

## Steps

### 1. Clone

```bash
git clone https://github.com/jagguvarma15/agent-deployments.git
cd agent-deployments
```

### 2. Pick a prototype and track

```bash
# List available prototypes
ls prototypes/

# Choose one — we'll use customer-support-triage as the example
cd prototypes/customer-support-triage/python   # or typescript
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in the required keys. Each `.env.example` is annotated with
comments explaining what each variable does.

### 4. Start everything

```bash
# From the prototype's language directory
docker compose up

# Or from the repo root using the Makefile
make up PROTOTYPE=customer-support-triage TRACK=python
```

This brings up:
- The agent API service
- Postgres 16
- Redis 7
- Qdrant (if needed by the prototype)
- Langfuse (tracing UI at http://localhost:3000)

### 5. Verify

```bash
# Health check
curl http://localhost:8000/health

# Try the main endpoint (varies by prototype — check the prototype's README)
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-jwt>" \
  -d '{"message": "I need to update my billing info", "user_id": "user-1"}'
```

### 6. View traces

Open http://localhost:3000 to see Langfuse traces for your request.

## Using the Makefile

The top-level `Makefile` provides shortcuts that work for any prototype:

```bash
make up PROTOTYPE=<name> TRACK=<python|typescript>    # Start services
make down PROTOTYPE=<name> TRACK=<python|typescript>   # Stop services
make test PROTOTYPE=<name> TRACK=<python|typescript>   # Run tests
make eval PROTOTYPE=<name> TRACK=<python|typescript>   # Run evals
make lint PROTOTYPE=<name> TRACK=<python|typescript>   # Run linter
make security PROTOTYPE=<name>                         # Run Promptfoo scan
```

## Troubleshooting

- **Port conflicts**: The default ports are 8000 (API), 5432 (Postgres), 6379 (Redis), 6333 (Qdrant), 3000 (Langfuse). Check for conflicts with `lsof -i :<port>`.
- **Docker memory**: Langfuse + Qdrant + Postgres can use 2-4 GB. Ensure Docker has enough memory allocated.
- **Missing env vars**: The app validates config at boot. If a required var is missing, you'll see a clear error message.

## Next steps

- Read the prototype's README for API docs and architecture details
- Check `docs/stack.md` for the full stack rationale
- See the prototype's `docs/swaps.md` for alternative picks
- Run `make eval` to see the evaluation suite in action
