# Cross-cutting Concerns

Shared production plumbing used by all agents. Each file answers: **"What production scaffolding do I need?"**

| Concern | Library (Py / TS) | Reference |
|---------|-------------------|-----------|
| [Auth](auth-jwt.md) | python-jose / hono-jwt | Inline implementation below |
| [Logging](logging-structured.md) | structlog / pino | Inline implementation below |
| [Observability](observability.md) | Langfuse SDK | Inline implementation below |
| [Rate Limiting](rate-limiting.md) | slowapi / hono-rate-limiter | Inline implementation below |
| [Testing](testing-strategy.md) | pytest + DeepEval / vitest + Promptfoo | Inline implementation below |
| [Idempotency](idempotency.md) | Redis `SET NX EX` + DB unique constraints | Two-phase claim, SETNX dedupe, outbound keys |
| [Resilience](resilience.md) | tenacity + pybreaker / p-retry + opossum | Retries, timeouts, circuit breakers, bulkheads |
| [Health & graceful shutdown](health-graceful-shutdown.md) | FastAPI lifespan + signal / Hono + process | Startup/liveness/readiness + SIGTERM drain |
| [Distributed locking](distributed-locking.md) | Redis `SET NX EX` + Lua / Postgres advisory | Use sparingly — prefer idempotency |

## The 11-point production checklist

Every blueprint specifies these concerns. See [playbook/production-checklist.md](../playbook/production-checklist.md) for the full checklist.
