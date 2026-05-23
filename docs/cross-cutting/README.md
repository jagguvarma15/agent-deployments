# Cross-cutting Concerns

Shared production plumbing used by all agents. Each file answers: **"What production scaffolding do I need?"**

| Concern | Library (Py / TS) | Reference |
|---------|-------------------|-----------|
| [Auth](auth-jwt.md) | python-jose / hono-jwt | Inline implementation below |
| [Logging](logging-structured.md) | structlog / pino | Inline implementation below |
| [Observability](observability.md) | Langfuse SDK | Inline implementation below |
| [Rate Limiting](rate-limiting.md) | slowapi / hono-rate-limiter | Inline implementation below |
| [Testing](testing-strategy.md) | pytest + DeepEval / vitest + Promptfoo | Inline implementation below |
| [Security hardening](security-hardening.md) | stdlib + `pip-audit` / `npm audit` / Trivy | OWASP for agents, prompt injection, deps, TLS, containers |
| [Authorization & RBAC](authorization-rbac.md) | stdlib enums + FastAPI / Hono; OPA optional | RBAC / ABAC / PBAC; per-intent tool allowlists; tenant scoping |
| [Audit logging](audit-logging.md) | Postgres `audit_events` + triggers; S3 archive | Immutable trail with hash-chain tamper evidence |
| [PII handling (GDPR)](pii-gdpr.md) | `pgcrypto` / KMS envelope + tokenization | Minimization, storage, erasure, LLM redaction, DLP |

## The 11-point production checklist

Every blueprint specifies these concerns. See [playbook/production-checklist.md](../playbook/production-checklist.md) for the full checklist.
