# Playbook: Production Checklist

Every blueprint in this repo specifies these 11 points. Use this as a gate before calling any agent "production-shaped."

## The checklist

1. **Containerized** — Multi-stage Dockerfile, <200 MB final image. See [`docs/reference/docker-templates.md`](../reference/docker-templates.md).
2. **Local up in one command** — `docker compose up` brings everything online. See [`docs/reference/docker-compose-template.md`](../reference/docker-compose-template.md).
3. **Config via env** — `.env.example` committed, validated at boot via pydantic-settings / Zod.
4. **Auth** — JWT-bearer on all agent endpoints (HS256 local, RS256 prod hint). See [`docs/cross-cutting/auth-jwt.md`](../cross-cutting/auth-jwt.md).
5. **Rate limiting** — Per-user and per-IP, Redis-backed (`slowapi` / `hono-rate-limiter`). See [`docs/cross-cutting/rate-limiting.md`](../cross-cutting/rate-limiting.md).
6. **Structured logging** — JSON with request/session/user context (`structlog` / `pino`). See [`docs/cross-cutting/logging-structured.md`](../cross-cutting/logging-structured.md).
7. **Tracing** — Every LLM call, tool call, and agent step traced in Langfuse. See [`docs/cross-cutting/observability.md`](../cross-cutting/observability.md).
8. **Persistence** — Conversation state in Postgres with managed migrations (Alembic / Drizzle). See [`docs/stack/relational-postgres.md`](../stack/relational-postgres.md).
9. **Tests** — Unit (mocked LLM), integration (real LLM), eval (golden datasets). See [`docs/cross-cutting/testing-strategy.md`](../cross-cutting/testing-strategy.md).
10. **CI** — Lint, typecheck, unit, eval, docker build, security scan via GitHub Actions. See [`docs/reference/ci-template.md`](../reference/ci-template.md).
11. **Docs** — Architecture diagram, API contract, eval docs per blueprint.

## How to check

For each point, verify against your implementation:

| # | Check | How to verify |
|---|-------|---------------|
| 1 | Containerized | `docker build -t my-agent .` succeeds, `docker images my-agent` shows <200 MB |
| 2 | Local up | `docker compose up` starts all services, `curl localhost:8000/health` returns 200 |
| 3 | Config via env | `.env.example` exists, app fails fast with clear error if required vars are missing |
| 4 | Auth | `curl localhost:8000/your-endpoint` returns 401, same with valid JWT returns 200 |
| 5 | Rate limiting | Rapid repeated requests return 429 after the configured limit |
| 6 | Structured logging | `docker compose logs app` shows JSON lines with `request_id`, `user_id` fields |
| 7 | Tracing | Open Langfuse (localhost:3000), make a request, see the trace with LLM + tool spans |
| 8 | Persistence | Make a request, restart the app, verify conversation state persists |
| 9 | Tests | Unit tests pass without API keys; integration tests pass with `ANTHROPIC_API_KEY` set |
| 10 | CI | Push to a branch, CI pipeline runs lint + typecheck + unit + docker build |
| 11 | Docs | README has architecture diagram, API contract section matches actual endpoints |

## Tiered adoption

You don't need all 11 points on day one. See the [tiered approach in the quickstart](../../docs/quickstart.md):

- **Tier 1 (working agent):** Points 3 (config), 9 (tests) — the minimum for a functioning prototype.
- **Tier 2 (API-ready):** Add points 1 (container), 2 (docker compose), 8 (persistence).
- **Tier 3 (production-shaped):** Add points 4-7 (auth, rate limiting, logging, tracing), 10 (CI), 11 (docs).
