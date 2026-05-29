---
id: obs.langfuse
kind: obs
provides: [tracing, llm_observability]
env_vars: [LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY]
docker:
  service: langfuse
  image: langfuse/langfuse:2
  ports: ["3001:3000"]
  environment:
    DATABASE_URL: "postgresql://agent:agent@postgres:5432/langfuse"
    NEXTAUTH_SECRET: "${LANGFUSE_NEXTAUTH_SECRET:-change-me}"
    SALT: "${LANGFUSE_SALT:-change-me}"
    NEXTAUTH_URL: "http://localhost:3001"
    TELEMETRY_ENABLED: "false"
  healthcheck:
    test: ["CMD-SHELL", "wget -qO- http://localhost:3000/api/public/health || exit 1"]
    interval: 10s
    timeout: 5s
    retries: 5
probe: langfuse_health
bootstrap_step: null
emit_files: []
docs: |
  Langfuse self-hosted LLM observability. Requires `relational.postgres` for
  its backing store; the resolver enforces this. Production should put NGINX
  in front and rotate NEXTAUTH_SECRET / SALT off the defaults.
---

# Capability: obs.langfuse

> Deep reference: [`stack/tracing-langfuse.md`](../../stack/tracing-langfuse.md). Vendor docs at https://langfuse.com/docs.

**Used for:** LLM observability — traces, scores, evals — self-hosted in compose alongside the agent.

## Why pick this

When self-hosted observability is a hard requirement (compliance, data residency, no SaaS dependency). Trades operational overhead for control. Pick `obs.langsmith` if you're already in the LangChain ecosystem and SaaS is fine.

## Local setup

The docker fragment above runs the Langfuse web image. It expects a `langfuse` database on the existing Postgres instance — the resolver enforces `relational.postgres` is on the recipe and adds a `CREATE DATABASE langfuse;` line to migrations.

Web UI: `http://localhost:3001`. On first visit, create the workspace + project; copy the public/secret keys into `.env.local` (the `wire_credentials` step prompts for them).

## Bootstrap

No automated bootstrap. Langfuse's first-run flow is interactive (creates the org + project + API keys via the web UI). Future Phase: add a `bootstrap_langfuse` step that uses the Langfuse provisioning API.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `LANGFUSE_HOST` | `http://localhost:3001` | Langfuse base URL |
| `LANGFUSE_PUBLIC_KEY` | *(from UI)* | Project public key — stored via keyring |
| `LANGFUSE_SECRET_KEY` | *(from UI, secret)* | Project secret key — stored via keyring |
| `LANGFUSE_NEXTAUTH_SECRET` | `change-me` | **Must rotate** in production |
| `LANGFUSE_SALT` | `change-me` | **Must rotate** in production |

## Cloud / production

- **Langfuse Cloud** at https://cloud.langfuse.com — managed; set `LANGFUSE_HOST=https://cloud.langfuse.com` and use the cloud keys.
- **Self-hosted production** — separate Postgres from the agent's, put NGINX/ALB in front, rotate `NEXTAUTH_SECRET` + `SALT`, enable HTTPS.

## When to swap it

- **→ `obs.langsmith`** if you want zero-ops and SaaS is acceptable.
- **→ `obs.grafana-stack`** if your trace target includes non-LLM services.

## See also

- `stack/tracing-langfuse.md` — full reference
- `capabilities/relational/postgres.md` — required dependency
