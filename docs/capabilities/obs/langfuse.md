---
id: obs.langfuse
kind: obs
implements:
  port: obs
  interface_version: "1.0"
layer: observability
requires: [relational.postgres]
bootstrap_inputs:
  database_name: langfuse
provides: [tracing, llm_observability, scoring]
env_vars: [LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_NEXTAUTH_SECRET, LANGFUSE_SALT]
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
  depends_on: [postgres]
  healthcheck:
    test: ["CMD-SHELL", "wget -qO- http://localhost:3000/api/public/health || exit 1"]
    interval: 10s
    timeout: 5s
    retries: 5
probe: langfuse_health
bootstrap_step: bootstrap_langfuse
provisioning_time: ~30s
cost_tier: free
est_tokens: 800
card:
  name: Langfuse
  description: "Self-hosted LLM observability with traces, scores, and dataset-backed evaluations."
  capabilities_provided: [llm_tracing, tool_call_tracing, scoring, eval_datasets]
  required_credentials: [LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY]
emit_files: []
docs: |
  Langfuse self-hosted LLM observability. Requires `relational.postgres` for
  its backing store. Bootstrap step creates the `langfuse` database; the
  web UI handles workspace + project + API-key creation on first visit.
tags: [observability, llm-tracing, self-hosted]
when_to_load: "recipe declares obs.langfuse"
verification:
  tier: T1
---

# Capability: obs.langfuse

> Deep reference: [`stack/tracing-langfuse.md`](../../stack/tracing-langfuse.md). Vendor docs at https://langfuse.com/docs.

**Used for:** LLM observability — traces, scores, evals — self-hosted in compose alongside the agent.

## Local setup

The docker fragment above runs the Langfuse web image. It connects to a `langfuse` database on the existing Postgres instance (created by the bootstrap step). Web UI: `http://localhost:3001`.

On first visit, create the workspace + project; copy the public/secret keys into `.env.local` (the `wire_credentials` step prompts for them).

## Bootstrap (post docker_up)

`bootstrap_langfuse`:

1. Connects to Postgres using the project's `DATABASE_URL` (server-level user).
2. Creates the `langfuse` database if it doesn't already exist.
3. Waits for the Langfuse healthcheck to pass.

```python
import psycopg2
conn = psycopg2.connect(server_url)
conn.autocommit = True
with conn.cursor() as cur:
    cur.execute("SELECT 1 FROM pg_database WHERE datname='langfuse'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE langfuse")
```

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `LANGFUSE_HOST` | `http://localhost:3001` | Langfuse base URL |
| `LANGFUSE_PUBLIC_KEY` | *(from UI)* | Project public key — stored via keyring |
| `LANGFUSE_SECRET_KEY` | *(from UI, secret)* | Project secret key — stored via keyring |
| `LANGFUSE_NEXTAUTH_SECRET` | `change-me` | **Must rotate** in production |
| `LANGFUSE_SALT` | `change-me` | **Must rotate** in production |

## Client integration

**Python (langfuse SDK):**

```python
from langfuse import Langfuse
from langfuse.decorators import observe

lf = Langfuse(
    public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
    secret_key=os.environ["LANGFUSE_SECRET_KEY"],
    host=os.environ["LANGFUSE_HOST"],
)

@observe()
async def run_agent(question: str) -> str:
    # Auto-captures input/output as a trace
    return await claude.messages.create(...)
```

**TypeScript (langfuse SDK):**

```ts
import { Langfuse } from "langfuse";

const lf = new Langfuse({
  publicKey: process.env.LANGFUSE_PUBLIC_KEY!,
  secretKey: process.env.LANGFUSE_SECRET_KEY!,
  baseUrl: process.env.LANGFUSE_HOST,
});

const trace = lf.trace({ name: "research", input: { question } });
const generation = trace.generation({ model: "claude-sonnet-4-6", input: messages });
// ... call the LLM ...
generation.end({ output: response });
trace.update({ output: response });
await lf.flushAsync();
```

## Cloud / production

- **Langfuse Cloud** at https://cloud.langfuse.com — managed. Set `LANGFUSE_HOST=https://cloud.langfuse.com` and use the cloud keys.
- **Self-hosted production** — separate Postgres from the agent's, put NGINX/ALB in front, rotate `NEXTAUTH_SECRET` + `SALT`, enable HTTPS.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `database "langfuse" does not exist` | Bootstrap step didn't run | Re-run `bootstrap_langfuse`; or `docker compose exec postgres createdb -U agent langfuse` |
| Web UI returns 500 on first load | Migrations still running | First-boot runs schema migration; wait 30-60s and refresh |
| `LANGFUSE_PUBLIC_KEY` not set | Created project in UI but didn't copy keys | Open `http://localhost:3001/project/<id>/settings`, copy keys into `.env.local` |
| Traces not appearing | Wrong env vars / wrong project | Verify `LANGFUSE_HOST` points at the running instance and keys belong to the project you're viewing |

## See also

- [`stack/tracing-langfuse.md`](../../stack/tracing-langfuse.md) — full reference
- [`capabilities/relational/postgres.md`](../relational/postgres.md) — required dependency
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
