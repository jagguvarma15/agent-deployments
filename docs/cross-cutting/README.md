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
| [Security hardening](security-hardening.md) | stdlib + `pip-audit` / `npm audit` / Trivy | OWASP for agents, prompt injection, deps, TLS, containers |
| [Authorization & RBAC](authorization-rbac.md) | stdlib enums + FastAPI / Hono; OPA optional | RBAC / ABAC / PBAC; per-intent tool allowlists; tenant scoping |
| [Audit logging](audit-logging.md) | Postgres `audit_events` + triggers; S3 archive | Immutable trail with hash-chain tamper evidence |
| [PII handling (GDPR)](pii-gdpr.md) | `pgcrypto` / KMS envelope + tokenization | Minimization, storage, erasure, LLM redaction, DLP |
| [Prompt management](prompt-management.md) | Langfuse `get_prompt` / LangSmith Hub / flat-file + git | Versioning, registry, A/B routing, rollback playbook |

## The 11-point production checklist

Every blueprint specifies these concerns. See [playbook/production-checklist.md](../playbook/production-checklist.md) for the full checklist.

## See also: cognitive-pattern lineage

These cross-cutting concerns are the operational layer that wraps the cognitive
patterns documented in the sister `agent-blueprints` repo. For the lineage map
between classical distributed-systems patterns and the agent patterns they
specialize — and for which classical patterns are explicitly scoped here rather
than there — see
[`agent-blueprints/foundations/system-design-heritage.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/foundations/system-design-heritage.md).
That doc links back into the files above for Circuit Breaker, Retry+Backoff,
Idempotency, and Distributed Tracing.
