# Playbook: Production Checklist

Every prototype in this repo implements these 11 points. Use this as a gate before calling any agent "production-shaped."

## The checklist

1. **Containerized** -- Multi-stage Dockerfile, <200 MB final image.
2. **Local up in one command** -- `docker compose up` brings everything online.
3. **Config via env** -- `.env.example` committed, validated at boot via pydantic-settings / Zod.
4. **Auth** -- JWT-bearer on all agent endpoints (HS256 local, RS256 prod hint).
5. **Rate limiting** -- Per-user and per-IP, Redis-backed (`slowapi` / `hono-rate-limiter`).
6. **Structured logging** -- JSON with request/session/user context (`structlog` / `pino`).
7. **Tracing** -- Every LLM call, tool call, and agent step traced in Langfuse.
8. **Persistence** -- Conversation state in Postgres with managed migrations (Alembic / Drizzle).
9. **Tests** -- Unit (mocked LLM), integration (real LLM), eval (golden datasets).
10. **CI** -- Lint, typecheck, unit, eval, docker build, security scan via GitHub Actions.
11. **Docs** -- README, architecture diagram, swap guide, eval docs per prototype.

## How to check

Run these from the repo root for any prototype:

```bash
# Does it start?
make up PROTOTYPE=<name> TRACK=<python|typescript>
make health

# Does it pass tests?
make test PROTOTYPE=<name> TRACK=<python|typescript>

# Does it pass linting?
make lint PROTOTYPE=<name> TRACK=<python|typescript>

# Does the image build standalone?
make docker-build PROTOTYPE=<name> TRACK=<python|typescript>

# Does it survive a red-team scan?
make security PROTOTYPE=<name>
```
