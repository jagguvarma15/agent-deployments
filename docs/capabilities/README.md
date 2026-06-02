# Capability catalog

Capabilities are the unit of consumption for `agent-scaffold`'s **Track C** project-platform features. A capability is a high-level infra need (e.g. `vector_db.qdrant`, `host.vercel`) that ships with everything required to provision and integrate it: env vars, a docker-compose fragment, an orchestrator bootstrap step id, optional file templates, and optional cloud-deploy hints.

Recipes opt in by declaring `capabilities:` in their frontmatter; `agent-scaffold` resolves each id against this catalog and threads the resolved set through context assembly, the orchestrator, and the generation prompt.

This catalog is consumed by `agent-scaffold` ≥ v0.3 (Phase 1b of Track C). On older scaffold versions the `capabilities:` field is silently ignored — recipes remain backwards-compatible.

## When to add a capability vs. extend stack/

- **stack/`<x>`.md** — deep reference doc for a stack pick: tradeoffs, every config knob, multi-paragraph integration patterns. Long-form. Human-first.
- **capabilities/`<kind>`/`<name>`.md** — machine-consumable provisioning recipe: frontmatter is the contract, body is a tight quickstart pointing back to the stack doc for depth.

Most stack picks should have a sibling capability so `agent-scaffold up` can stand them up. The two layers cross-link.

## Directory layout

```
docs/capabilities/
  README.md                 # this file
  vector_db/                # kind = vector_db
    qdrant.md
    chroma.md
    pgvector.md
  cache/                    # kind = cache
    redis.md
  relational/               # kind = relational
    postgres.md
  queue/                    # kind = queue
    kafka.md
    redis-streams.md
  obs/                      # kind = obs
    langsmith.md
    langfuse.md
    grafana-stack.md
  eval/                     # kind = eval (may carry templates/)
    promptfoo.md
  frontend/                 # kind = frontend (may carry templates/)
    nextjs-chat.md
    streamlit.md
  host/                     # kind = host (cloud target; deploy_configs)
    vercel.md
    railway.md
    fly.md
```

The dotted capability id always matches the path: `vector_db.qdrant` ⇄ `vector_db/qdrant.md`.

## Frontmatter schema

```yaml
---
id: vector_db.qdrant                 # required — dotted: <kind>.<name>; must match file path
kind: vector_db                      # required — one of: vector_db | cache | relational | queue | obs | eval | frontend | host
provides: [embeddings_store]         # optional — free-form capability tags used for substitution / dedup
env_vars: [QDRANT_URL, QDRANT_API_KEY]   # canonical env var names the generated app must reference
docker:                              # optional — omit for managed-only services
  service: qdrant                    # service name in the merged docker-compose.yml
  image: qdrant/qdrant:v1.12.0       # pinned tag, never :latest
  ports: ["6333:6333", "6334:6334"]
  volumes: ["qdrant_data:/qdrant/storage"]
  environment: {}                    # service-level env overrides
  healthcheck:                       # optional, but recommended
    test: ["CMD-SHELL", "wget -qO- http://localhost:6333/healthz || exit 1"]
    interval: 5s
    timeout: 5s
    retries: 5
probe: qdrant_collections            # name of a probe in agent_scaffold.probes.PROBES (Phase 2 may add it)
bootstrap_step: bootstrap_vector_db  # orchestrator step that initializes the service post docker_up
emit_files: []                       # paths under templates/ to copy verbatim into project (frontend caps mainly)
deploy_configs: []                   # for host.* capabilities only — see "Host capability shape" below
docs: |                              # short markdown block injected into the LLM context tier
  Free-form. One paragraph max — depth lives in the body below the frontmatter
  and in the linked stack/ doc.
---
```

### Required fields

| Field | Notes |
|-------|-------|
| `id` | Dotted `<kind>.<name>`. Lowercase, `_` separator inside each part allowed (`vector_db.pgvector`). Must equal the file path under `capabilities/`. |
| `kind` | One of the 8 enumerated kinds. Adding a new kind needs an `agent-scaffold` change too (Phase 1b enum) — coordinate before introducing. |
| `env_vars` | List of canonical environment variable names. The generated app and `.env.example` must use exactly these names. |

### Optional fields

| Field | When to set it |
|-------|----------------|
| `provides` | Use for capability dedup. Two capabilities providing `embeddings_store` are treated as substitutes (resolver picks the first declared on the recipe). |
| `docker` | Whenever the service can run locally in compose. Omit for purely managed services (e.g. some `host.*` and `obs.langsmith`). |
| `probe` | Name of a probe function. If the probe doesn't yet exist in agent-scaffold, leave a comment in the brief — Phase 2 fills in any gaps. |
| `bootstrap_step` | Required when post-`docker_up` initialization is needed (creating collections, topics, datasources). Omit for "compose up is sufficient" services like Redis. |
| `emit_files` | List of `{source, dest}` pairs. `source` is relative to the capability's directory; `dest` is relative to project root. Glob `**` supported. |
| `deploy_configs` | Only for `kind: host`. See below. |

## Frontend capability shape

Frontend capabilities ship file trees under `templates/` next to the markdown:

```
docs/capabilities/frontend/
  nextjs-chat.md
  templates/
    nextjs-chat/
      package.json
      app/page.tsx
      ...
```

Their frontmatter should declare:

```yaml
emit_files:
  - source: templates/nextjs-chat/**
    dest: frontend/
```

The scaffold's copier (Phase 3b) walks the glob and recreates the structure under `dest`. It never overwrites files the model emitted in the same path — the LLM's specialization wins.

## Host capability shape

Host capabilities target a cloud provider. They typically have no `docker` block:

```yaml
id: host.vercel
kind: host
env_vars: [VERCEL_TOKEN, VERCEL_ORG_ID, VERCEL_PROJECT_ID]
deploy_configs:
  - target: vercel
    cli_cmd: "vercel deploy --prod"
    dashboard_url: "https://vercel.com/dashboard"
    config_file: vercel.json          # emitted by the emit_deploy_configs step
emit_files:
  - source: templates/vercel.json
    dest: vercel.json
```

The `target` string matches what `agent-scaffold deploy --target <name>` expects.

## Versioning

The catalog has no schema version field today. The Phase 1b loader treats unknown keys as warnings (not errors) so additive fields can land without breaking older scaffolds. If a breaking change is needed, add `schema_version: 2` to the affected files and coordinate a scaffold release.

## Authoring checklist

When adding or updating a capability:

- [ ] `id` exactly matches the file path under `capabilities/`
- [ ] `kind` is one of the 8 enumerated kinds
- [ ] `env_vars` are CANONICAL (no project-specific prefixes) — the generated app uses these names verbatim
- [ ] If `docker:` is set, image tag is pinned (no `:latest`)
- [ ] If a sibling exists under `stack/<x>.md`, cross-link both directions (one-line `Capability:` header on the stack doc; "See also: stack/x.md" line in the capability body)
- [ ] Body has: H1 title, 1-paragraph "Why pick this", "Local setup" (compose snippet quoted from frontmatter or expanded), "Production / cloud" pointer, "Env vars" table, "When to swap it" (1–2 sentences)
- [ ] Body stays under ~120 lines — depth lives in `stack/`

## Recipe usage

A recipe opts into capabilities via the `capabilities:` field in its frontmatter:

```yaml
# docs/recipes/restaurant-rebooking.md
---
capabilities:
  - cache.redis
  - relational.postgres
  - vector_db.qdrant
---
```

The scaffold's context assembler injects each capability's body under a `## Capability: <id>` header so the LLM sees consistent infra context regardless of which recipe pulls it in.

The full recipe-frontmatter schema (every field, type, requiredness, consumer version) is documented in [`../recipes/SCHEMA.md`](../recipes/SCHEMA.md). The `capabilities:` field is one of several — see SCHEMA.md for the rest, including `bootstrap_config:` inputs that this catalog's bootstrap steps read at provisioning time.

## See also

- `docs/stack/` — long-form stack picks. Most capabilities have a sibling here.
- `docs/blueprint-map.md` — recipe → pattern mapping (capabilities are layered on top, orthogonally).
