# Playbook: Production Checklist

Every blueprint in this repo specifies these 16 points. Use this as a gate before calling any agent "production-shaped."

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
12. **MCP wired** — Every external tool the agent invokes goes through an MCP server (server stub committed if custom). Recipe declares `mcp_servers:` in frontmatter; generated project ships `mcp.json` + per-server launcher.
13. **Skills declared** — Repeatable in-context procedures live as discoverable skills, not inline prompt fragments. Recipe declares `skills:` in frontmatter; each skill ships a `SKILL.md` + optional helper scripts.
14. **Trajectory eval** — Eval suite scores BOTH end-to-end success AND the path taken (tool order, retry count, hallucinated tool calls). The agent that reaches a correct answer through dangerous or inefficient tool calls still represents a production failure.
15. **Guardrails layer** — At least one capability from `kind: guardrail` runs in front of the agent's tool-call surface. Inbound prompt-injection and outbound PII checks pass. Recipe declares `guardrails:` in frontmatter.
16. **Sandbox for code execution** — Any agent that runs LLM-emitted code does it inside a `kind: sandbox` capability (E2B / Modal / Daytona). Recipe declares `sandbox:` in frontmatter when applicable.

### Conditional follow-ups

These are not blocking criteria — they apply when the recipe's shape makes them load-bearing:

- **Durable workflow** *(if the agent's success criterion can take longer than 30 seconds)*: a `kind: durable` capability (Temporal / Inngest / Restate) journals every step so the agent can resume from exactly where it stopped, regardless of what crashed. Recipe declares `durable_workflow:` in frontmatter.
- **OTel `gen_ai.*` semconv** *(when tracing exists)*: spans use the [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) (`gen_ai.request.model`, `gen_ai.token.usage`, `gen_ai.system`, …), not generic attribute names. Langfuse, Datadog, Honeycomb, and Phoenix all consume these.

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
| 12 | MCP wired | `mcp.json` exists in repo root; every entry resolves to a reachable server (probe passes) |
| 13 | Skills declared | `skills/<id>/SKILL.md` exists per `skills:` entry; loader registers each one at boot |
| 14 | Trajectory eval | `make trajectory-eval` (or equivalent) scores recent runs against a rubric of step order + tool-call validity |
| 15 | Guardrails layer | A canned prompt-injection input is rejected by the inbound guardrail; a canned PII output is rejected by the outbound guardrail |
| 16 | Sandbox for code execution | LLM-emitted code that attempts `rm -rf /` (or similar) is contained — host filesystem unaffected; sandbox session ends without escape |

## Tiered adoption

You don't need all 16 points on day one. See the [tiered approach in the quickstart](../../docs/quickstart.md):

- **Tier 1 (working agent):** Points 3 (config), 9 (tests), 13 (skills) — the minimum for a functioning prototype.
- **Tier 2 (API-ready):** Add points 1 (container), 2 (docker compose), 8 (persistence), 12 (MCP).
- **Tier 3 (production-shaped):** Add points 4-7 (auth, rate limiting, logging, tracing), 10 (CI), 11 (docs), 14 (trajectory eval), 15 (guardrails), 16 (sandbox if the agent executes code).
