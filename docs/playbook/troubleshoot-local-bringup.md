# Local bring-up: cross-capability troubleshooting

When `docker compose up && make smoke` fails on a freshly-generated project, the failure usually crosses capability boundaries — Langfuse can't reach its database, vector collections fail to create against an unready Qdrant, the app boots before `wire_credentials` finishes. Per-capability docs cover their own failure modes; this guide covers the failures that span multiple capabilities.

The structure mirrors `LAYER_ORDER`: each section walks the failures specific to that layer's interaction with everything below it.

---

## Bootstrap-order failures

### Layer `observability` cannot reach layer `infrastructure`

**Symptom:** Langfuse container restarts in a loop; logs say `connect ECONNREFUSED postgres:5432` or `database "langfuse" does not exist`.

**Cause:** The `langfuse` database hasn't been created yet, even though Postgres is healthy. `obs.langfuse` declares `requires: [relational.postgres]` and `bootstrap_inputs: {database_name: langfuse}` — the bootstrap step must create that database before Langfuse can start.

**Fix:**
```bash
# Manually create the database:
docker compose exec postgres createdb -U agent langfuse

# Then restart Langfuse:
docker compose restart langfuse

# Or re-run the bootstrap step:
agent-scaffold up --resume bootstrap_langfuse
```

For a permanent fix, confirm `bootstrap_langfuse` is in the layered orchestration plan and runs between the `schema` and `observability` layers.

### Layer `data` runs before layer `infrastructure` is healthy

**Symptom:** `bootstrap_vector_db` fails with `Connection refused` to Qdrant, or `pgvector` extension creation errors with `database not accepting connections`.

**Cause:** Compose's `depends_on: condition: service_healthy` waits for the container's healthcheck, but the bootstrap step runs from the host and races the healthcheck-to-API-ready gap. Qdrant's `/healthz` returns 200 before the gRPC port (6334) is fully listening.

**Fix:**
```bash
# Wait for the API to be ready, not just the container:
until curl -sf http://localhost:6333/collections >/dev/null; do
  echo "waiting for qdrant API..."
  sleep 2
done

# Then re-run bootstrap:
agent-scaffold up --resume bootstrap_vector_db
```

For a permanent fix, the bootstrap step should poll the *application-level* health endpoint with retries, not depend on Docker's healthcheck alone.

### Layer `agent` boots before credentials are wired

**Symptom:** Agent process crashes with `KeyError: 'ANTHROPIC_API_KEY'` or `TAVILY_API_KEY not found`.

**Cause:** `wire_credentials` step prompts for SaaS keys interactively but the agent service in compose starts immediately. The agent reads env vars at boot.

**Fix:**
```bash
# Stop the agent if it's already started:
docker compose stop agent

# Run wire_credentials explicitly:
agent-scaffold up --resume wire_credentials

# Restart agent with the new env:
docker compose up -d agent
```

For a permanent fix, the agent service in compose should declare `depends_on:` for the secrets file the `wire_credentials` step writes (e.g. `.env.local`), so it doesn't start until that file exists.

---

## Env-coordination failures

### `DATABASE_URL` points at the wrong port

**Symptom:** App connects to Postgres successfully from the host but not from inside compose, or vice versa.

**Cause:** The recipe's `env_contract` includes one `DATABASE_URL` but compose-internal connections use `postgres:5432` while host connections use `localhost:5432`. The `.env.example` defaults to host syntax.

**Fix:** Use the in-compose hostname inside compose:
```bash
# .env (used by services in compose):
DATABASE_URL=postgresql+asyncpg://agent:agent@postgres:5432/agent_db

# .env.local (used by `make dev` running on host):
DATABASE_URL=postgresql+asyncpg://agent:agent@localhost:5432/agent_db
```

The scaffold's `wire_credentials` step distinguishes between these two contexts and writes both.

### Langfuse public/secret keys not set after first boot

**Symptom:** Agent traces don't appear in Langfuse UI; agent logs show `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are empty.

**Cause:** Langfuse's first-run flow is interactive: create workspace → create project → copy keys. The bootstrap step doesn't automate this; the user must open `http://localhost:3001`, set up the project, and paste keys back into `.env.local`.

**Fix:**
```bash
# 1. Open Langfuse UI
open http://localhost:3001

# 2. After creating the project, run wire_credentials to capture keys:
agent-scaffold auth login --provider langfuse

# 3. Restart the agent:
docker compose restart agent
```

### `wire_credentials` prompts for keys you don't have yet

**Symptom:** Bring-up halts asking for `OPENAI_API_KEY` but you're running an all-local recipe (no embeddings via SaaS).

**Cause:** The recipe's `default` runtime_mode declared `embedding.openai`, which carries `OPENAI_API_KEY` in its env_vars. The keys-required prompt is derived from the resolved capability set.

**Fix:** Switch runtime mode:
```bash
agent-scaffold up --mode local_only
# or, override the capability:
agent-scaffold up --override embedding.openai=embedding.local-bge
```

The `runtime_modes` block on the recipe enumerates which swaps each mode applies. See [`docs/recipes/SCHEMA.md`](../recipes/SCHEMA.md#runtime_modes).

---

## Capability-substitution failures (`runtime_modes`)

### `local_only` mode swaps to a local LLM but the model isn't pre-pulled

**Symptom:** Agent boot fails with `Model 'llama-3.1-8b' not found` or `Connection refused` to the local LLM endpoint.

**Cause:** A `local_only` swap pointed at `stack/llm-local-ollama` but Ollama hasn't pulled the model.

**Fix:**
```bash
# Pre-pull the model:
ollama pull llama3.1:8b

# Or run the model docker image with auto-pull:
docker compose run --rm ollama ollama pull llama3.1:8b

# Verify it's available:
curl http://localhost:11434/api/tags
```

For first-time `local_only` runs, allow ~10 minutes for the model pull on first use.

### Vector dimension mismatch after embedding swap

**Symptom:** `Vector dimension mismatch (expected 1536, got 768)` after switching embedding providers.

**Cause:** Vector collections were created at 1536 dim (OpenAI default) but the swap is to `embedding.local-bge` (768 dim). Existing vectors are incompatible with the new model.

**Fix:**
```bash
# Drop and recreate at the new dim:
curl -X DELETE http://localhost:6333/collections/docs
agent-scaffold up --resume bootstrap_vector_db

# Re-ingest content with the new embedding model:
make ingest
```

For permanent fixes, declare `vector_collections[].vector_size` in the recipe frontmatter and the bootstrap step will refuse to overwrite an existing collection with a different size — surfacing the issue before re-ingest is needed.

---

## Resource-budget failures

### Docker out of memory when running the full stack

**Symptom:** Random container restarts; `dmesg` shows `Killed process ... out of memory`.

**Cause:** Langfuse + Qdrant + Postgres + Kafka + agent + frontend can exceed 8 GB on default Docker Desktop settings. Vector ops + Kafka JVM are the largest consumers.

**Fix:**
1. Raise Docker Desktop memory cap to 12 GB (Settings → Resources → Memory).
2. Or trim the recipe: swap `queue.kafka` for `queue.redis-streams`, swap `obs.langfuse` for `obs.langsmith`. Both swaps belong in a recipe's `runtime_modes.lightweight` if memory-constrained dev is a regular use case.

### Port conflicts with host-side services

**Symptom:** `docker compose up` fails with `bind: address already in use` on port 8000, 5432, 6379, etc.

**Cause:** Common ports collide with host-running services (a host Postgres on 5432, host FastAPI on 8000, Chroma's default 8000 colliding with FastAPI's 8000).

**Fix:**
```bash
# Identify the conflict:
lsof -i :8000

# Stop the host service or remap the container port in compose:
ports:
  - "8002:8000"   # Chroma on host 8002 instead

# Update CHROMA_URL accordingly:
CHROMA_URL=http://localhost:8002
```

Default port assignments live in each capability's `docker.ports[]`. Recipes can override via `env_overrides` for host-side port mapping.

---

## Health-check stalemates

### Langfuse healthy but UI returns 500 on first load

**Symptom:** `docker compose ps` shows langfuse as `healthy`, but visiting `http://localhost:3001` returns `500 Internal Server Error`.

**Cause:** Langfuse runs database migrations on first boot; the migration takes 30-60s. The healthcheck endpoint (`/api/public/health`) passes earlier than the schema is ready.

**Fix:** Wait, then refresh. If it persists past 2 minutes:
```bash
# Check migration progress:
docker compose logs langfuse | grep -i migration

# Reset Langfuse's database and re-bootstrap:
docker compose exec postgres dropdb -U agent langfuse
docker compose exec postgres createdb -U agent langfuse
docker compose restart langfuse
```

### Temporal healthcheck passes but workflows queue forever

**Symptom:** `tctl cluster health` returns OK, but workflows submitted to a task queue stay in `Started` indefinitely.

**Cause:** Temporal cluster is up but no worker is polling the task queue. Workers run as separate processes the agent project spawns.

**Fix:**
```bash
# Confirm the worker process is running:
docker compose ps agent-worker

# If absent, the recipe's compose file is missing the worker service.
# Verify the recipe declares both:
#   - agent service (HTTP)
#   - agent-worker service (polls Temporal)
```

For permanent fixes, the recipe's `required_files` should include a `worker.py` (Python) or `worker.ts` (TypeScript) entry point + a corresponding compose service.

---

## Diagnostics workflow

When local bring-up fails, walk this checklist in order:

1. **Is every container healthy?** `docker compose ps` — all status columns should read `healthy` or `running`. Anything in `restarting` means look at its logs.

2. **Did the bootstrap steps run?** `agent-scaffold up --plan` reprints the executed plan. Any step in `pending` after bring-up needs `--resume <step-name>`.

3. **Are the env vars present in the running containers?** `docker compose exec agent env | grep -E '(DATABASE|REDIS|LANGFUSE|ANTHROPIC)_'`. Missing keys mean `wire_credentials` was skipped or `.env.local` wasn't sourced.

4. **Is the smoke test failing on the agent or its dependencies?** Run the `smoke_test.ready` command first; if it succeeds but `exercise` fails, the problem is in the agent process. If `ready` fails, walk up the layer chain.

5. **Does the per-capability `## Troubleshoot` section name the failure?** Each capability doc has a 4-row symptom table covering its single-capability failure modes. Cross-capability failures live here.

---

## See also

- [`agents.md`](../../agents.md) "Bringing a recipe up locally" — the canonical 6-step consumer algorithm
- [`docs/recipes/SCHEMA.md`](../recipes/SCHEMA.md) — recipe frontmatter contract (`runtime_modes`, `smoke_test`, `cost_profile`)
- [`docs/capabilities/README.md`](../capabilities/README.md) — capability frontmatter contract (`layer`, `requires`, `bootstrap_inputs`)
- [`MANIFEST_SCHEMA.md`](../../MANIFEST_SCHEMA.md) `LAYER_ORDER` — bootstrap-sequencing contract
