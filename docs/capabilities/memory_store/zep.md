---
id: memory_store.zep
kind: memory_store
provides: [long_term_memory, semantic_recall, conversation_summarization]
env_vars: [ZEP_API_URL, ZEP_API_KEY]
docker:
  service: zep
  image: ghcr.io/getzep/zep:latest
  ports: ["8000:8000"]
  environment:
    ZEP_STORE_TYPE: postgres
    ZEP_STORE_POSTGRES_DSN: "postgres://agent:agent@postgres:5432/zep?sslmode=disable"
    ZEP_AUTH_REQUIRED: "true"
    ZEP_AUTH_SECRET: "${ZEP_AUTH_SECRET:-change-me}"
  depends_on: [postgres]
  healthcheck:
    test: ["CMD-SHELL", "wget -qO- http://localhost:8000/healthz || exit 1"]
    interval: 10s
    timeout: 5s
    retries: 5
probe: zep_health
bootstrap_step: bootstrap_zep
emit_files: []
docs: |
  Zep as the long-term memory store for `primitives: [memory]` recipes.
  Zep persists conversation history, summarizes long threads into facts, and
  exposes semantic search over the agent's recall surface. The OSS image runs
  alongside Postgres in compose. For the SaaS alternative, swap to
  `memory_store.zep-cloud`.
---

# Capability: memory_store.zep

> First-run setup: [`getting-started/zep.md`](../../getting-started/zep.md). Vendor: https://www.getzep.com.

**Used for:** Persistent agent memory across sessions — conversation history, summarized facts, semantic recall.

## Why pick this

When a recipe declares `primitives: [memory]`, it needs a backing store. Zep is the most agent-native option as of 2026 — built-in summarization (no separate LLM call from the agent code), session/user scoping, and a semantic-search index over both messages and derived facts.

Lighter alternatives: `memory_store.mem0` (planned), `memory_store.letta` (planned, formerly MemGPT). Heaviest (and most flexible): use `vector_db.qdrant` directly and roll your own memory primitives.

## Local setup

The compose fragment runs Zep against the existing Postgres. The bootstrap step creates the `zep` database on Postgres if missing and calls Zep's `/api/v1/users` endpoint to create the per-tenant user record (or no-op if it exists).

Web admin: `http://localhost:8000/admin`. Rotate `ZEP_AUTH_SECRET` off the default in production.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `ZEP_API_URL` | `http://zep:8000` | Zep API base URL |
| `ZEP_API_KEY` | *(generated)* | API key issued by Zep on first boot |
| `ZEP_AUTH_SECRET` | `change-me` | JWT signing secret — **must rotate** |

## Bootstrap

`bootstrap_zep` (a) ensures the `zep` Postgres database exists, (b) waits for Zep's health endpoint, (c) calls Zep to create the per-tenant user.

## Cloud / production

- **Zep Cloud** at https://app.getzep.com — managed. Set `ZEP_API_URL=https://api.getzep.com` and provide the cloud key.
- **Self-hosted production** — separate Postgres for Zep, rotate `ZEP_AUTH_SECRET`, set `ZEP_AUTH_REQUIRED=true` (the default).

## When to swap it

- **→ `memory_store.zep-cloud`** — managed Zep, same API surface.
- **→ `memory_store.mem0`** — lighter weight, less summarization machinery.
- **→ `vector_db.qdrant`** — roll your own memory primitives over a raw vector store.

## See also

- [`vendored/blueprints/primitives/memory/overview.md`](../../../vendored/blueprints/primitives/memory/overview.md) — pattern-level guidance.
- [`relational/postgres.md`](../relational/postgres.md) — required dependency.
