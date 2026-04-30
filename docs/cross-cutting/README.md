# Cross-cutting Concerns

Shared production plumbing used by all prototypes. Each file answers: **"What production scaffolding do I need?"**

| Concern | Library (Py / TS) | Lives in |
|---------|-------------------|----------|
| [Auth](auth-jwt.md) | python-jose / hono-jwt | `common/auth` |
| [Logging](logging-structured.md) | structlog / pino | `common/logging` |
| [Observability](observability.md) | Langfuse SDK | `common/observability` |
| [Rate Limiting](rate-limiting.md) | slowapi / hono-rate-limiter | `common/rate-limit` |
| [Testing](testing-strategy.md) | pytest + DeepEval / vitest + Promptfoo | `tests/` in each prototype |

## The 11-point production checklist

Every prototype implements these concerns. See [playbook/production-checklist.md](../playbook/production-checklist.md) for the full checklist.
