---
id: memory_store.zep
kind: memory_store
layer: data
requires: [relational.postgres]
bootstrap_inputs:
  database_name: zep
provides: [long_term_memory, semantic_recall, conversation_summarization]
env_vars: [ZEP_API_URL, ZEP_API_KEY, ZEP_AUTH_SECRET]
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
provisioning_time: ~30s
cost_tier: free
est_tokens: 700
card:
  name: Zep
  description: "Long-term agent memory store with conversation summarization, session/user scoping, and semantic recall."
  capabilities_provided: [long_term_memory, semantic_recall, conversation_summarization, session_scoping]
  required_credentials: [ZEP_API_KEY]
emit_files: []
docs: |
  Zep as the long-term memory store for `primitives: [memory]` recipes.
  Persists conversation history, summarizes long threads into facts, and
  exposes semantic search over the agent's recall surface. OSS image runs
  alongside Postgres in compose.
tags: [memory_store, long-term-memory, hosted]
when_to_load: "recipe declares memory_store.zep"
---

# Capability: memory_store.zep

> First-run setup: [`getting-started/zep.md`](../../getting-started/zep.md). Vendor: https://www.getzep.com.

**Used for:** Persistent agent memory across sessions — conversation history, summarized facts, semantic recall.

## Local setup

The compose fragment runs Zep against the existing Postgres. The bootstrap step creates the `zep` database and the per-tenant user record on first run.

Web admin: `http://localhost:8000/admin`. Rotate `ZEP_AUTH_SECRET` off the default in production.

## Bootstrap (post docker_up)

`bootstrap_zep`:

1. Ensures the `zep` Postgres database exists.
2. Waits for Zep's `/healthz` to return OK.
3. Calls Zep to create the per-tenant user.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `ZEP_API_URL` | `http://zep:8000` | Zep API base URL |
| `ZEP_API_KEY` | *(generated)* | API key issued by Zep on first boot |
| `ZEP_AUTH_SECRET` | `change-me` | JWT signing secret — **must rotate** |

## Client integration

**Python (zep-python):**

```python
from zep_python.client import AsyncZep

zep = AsyncZep(api_key=os.environ["ZEP_API_KEY"], base_url=os.environ["ZEP_API_URL"])

# Add user + session
await zep.user.add(user_id="user-1", email="user@example.com")
await zep.memory.add_session(session_id="session-1", user_id="user-1")

# Persist message history
await zep.memory.add(
    session_id="session-1",
    messages=[{"role": "user", "content": "What's the GraphQL vs gRPC debate?"}],
)

# Retrieve with semantic search
results = await zep.memory.search_sessions(
    session_id="session-1",
    text="streaming APIs",
    limit=5,
)
```

**TypeScript (@getzep/zep-cloud):**

```ts
import { ZepClient } from "@getzep/zep-cloud";

const zep = new ZepClient({ apiKey: process.env.ZEP_API_KEY!, baseURL: process.env.ZEP_API_URL });

await zep.user.add({ userId: "user-1", email: "user@example.com" });
await zep.memory.addSession({ sessionId: "session-1", userId: "user-1" });

await zep.memory.add("session-1", {
  messages: [{ role: "user", content: "What's the GraphQL vs gRPC debate?" }],
});

const results = await zep.memory.searchSessions({
  sessionId: "session-1",
  text: "streaming APIs",
  limit: 5,
});
```

## Cloud / production

- **Zep Cloud** at https://app.getzep.com — managed. Set `ZEP_API_URL=https://api.getzep.com` and provide the cloud key.
- **Self-hosted production** — separate Postgres for Zep, rotate `ZEP_AUTH_SECRET`, keep `ZEP_AUTH_REQUIRED=true`.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `connection refused 8000` | Zep not up yet | `docker compose logs zep` — wait for "Server listening" |
| `database "zep" does not exist` | bootstrap_zep didn't run | `docker compose exec postgres createdb -U agent zep` |
| `401 unauthorized` (cloud) | Wrong key tier | Cloud keys are project-scoped; recreate per project |
| Summarization quality poor | Default summarizer uses small model | Configure a stronger summarizer via Zep env vars (see vendor docs) |

## See also

- [`vendored/blueprints/primitives/memory/overview.md`](../../../vendored/blueprints/primitives/memory/overview.md) — primitive overview
- [`capabilities/relational/postgres.md`](../relational/postgres.md) — required dependency
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
