# Cross-cutting Concerns

Shared production plumbing used by all agents. Each file answers: **"What production scaffolding do I need?"**

| Concern | Library (Py / TS) | Reference |
|---------|-------------------|-----------|
| [Auth](auth-jwt.md) | python-jose / hono-jwt | Inline implementation below |
| [Logging](logging-structured.md) | structlog / pino | Inline implementation below |
| [Observability](observability.md) | Langfuse SDK | Inline implementation below |
| [Rate Limiting](rate-limiting.md) | slowapi / hono-rate-limiter | Inline implementation below |
| [Testing](testing-strategy.md) | pytest + DeepEval / vitest + Promptfoo | Inline implementation below |

## The 11-point production checklist

Every blueprint specifies these concerns. See [playbook/production-checklist.md](../playbook/production-checklist.md) for the full checklist.
