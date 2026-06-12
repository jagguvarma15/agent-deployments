# Capability catalog

Capabilities are the unit of consumption for `agent-scaffold`'s **Track C** project-platform features. A capability is a high-level infra need (e.g. `vector_db.qdrant`, `host.vercel`) that ships with everything required to provision and integrate it: env vars, a docker-compose fragment, an orchestrator bootstrap step id, optional file templates, and optional cloud-deploy hints.

Recipes opt in by declaring `capabilities:` in their frontmatter; `agent-scaffold` resolves each id against this catalog and threads the resolved set through context assembly, the orchestrator, and the generation prompt.

This catalog is consumed by `agent-scaffold` ≥ v0.3 (Phase 1b of Track C). On older scaffold versions the `capabilities:` field is silently ignored — recipes remain backwards-compatible.

> **Machine-readable index:** This directory's contents are aggregated into the top-level [`catalog.yaml`](../../catalog.yaml). If you're building a tool that consumes this repo, read the catalog rather than walking these files directly. See [`MANIFEST_SCHEMA.md`](../../MANIFEST_SCHEMA.md).

## When to add a capability vs. extend stack/

- **stack/`<x>`.md** — deep reference doc for a stack pick: tradeoffs, every config knob, multi-paragraph integration patterns. Long-form. Human-first.
- **capabilities/`<kind>`/`<name>`.md** — machine-consumable provisioning recipe: frontmatter is the contract, body is a tight quickstart pointing back to the stack doc for depth.

Most stack picks should have a sibling capability so `agent-scaffold up` can stand them up. The two layers cross-link.

## Directory layout

```
docs/capabilities/
  README.md                 # this file
  TEMPLATES.md              # template-tree convention (see below)
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
    templates/
      grafana-stack/        # prometheus.yml, tempo.yaml, dashboards/
  eval/                     # kind = eval (may carry templates/)
    promptfoo.md
    templates/
      promptfoo/            # promptfooconfig.yaml, cases.yaml
  frontend/                 # kind = frontend (may carry templates/)
    nextjs-chat.md
    streamlit.md
    templates/
      nextjs-chat/          # full Next.js scaffold
      streamlit/            # Streamlit app
  host/                     # kind = host (cloud target; deploy_configs)
    vercel.md
    railway.md
    fly.md
    templates/
      vercel/               # vercel.json, .vercelignore
      railway/              # railway.json, .railwayignore
      fly/                  # fly.toml, .dockerignore
```

The dotted capability id always matches the path: `vector_db.qdrant` ⇄ `vector_db/qdrant.md`. Template trees, when present, sit as `<kind>/templates/<name>/` siblings — see [`TEMPLATES.md`](TEMPLATES.md) for the contract.

## Frontmatter schema

```yaml
---
id: vector_db.qdrant                 # required — dotted: <kind>.<name>; must match file path
kind: vector_db                      # required — one of 16 known kinds (see "Capability kinds" below)
layer: data                          # required — one of catalog.LAYER_ORDER; drives bootstrap sequencing
provides: [embeddings_store]         # optional — free-form capability tags used for substitution / dedup
requires: []                         # optional — other capability ids this one depends on (id-resolved)
bootstrap_inputs: {}                 # optional — map of values this capability's bootstrap step expects from its requires deps
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
provisioning_time: ~10s              # coarse estimate ("instant", "~10s", "~60s", "~5min")
cost_tier: free                      # one of: free | fixed-monthly | per-call
est_tokens: 450                      # coarse estimate of doc's whole-file token cost
emit_files: []                       # paths under templates/ to copy verbatim into project (frontend caps mainly)
deploy_configs: []                   # for host.* capabilities only — see "Host capability shape" below
card:                                # required — MCP-Server-Card-style discovery metadata
  name: Qdrant
  description: "Self-hosted vector database with first-class HTTP/gRPC clients and named collections."
  capabilities_provided: [vector_search, hybrid_search, payload_filtering]
  required_credentials: []           # for hosted/SaaS capabilities, list env vars carrying secrets
tags: [vector-search, retrieval, self-hosted]    # optional — hybrid-intake discovery tokens
when_to_load: "recipe declares vector_db.qdrant" # optional — one-line predicate
docs: |                              # short markdown block injected into the LLM context tier
  Free-form. One paragraph max — depth lives in the body below the frontmatter
  and in the linked stack/ doc.
---
```

### Required fields

| Field | Notes |
|-------|-------|
| `id` | Dotted `<kind>.<name>`. Lowercase, `_` separator inside each part allowed (`vector_db.pgvector`). Must equal the file path under `capabilities/`. |
| `kind` | One of the 16 known kinds. Adding a new kind is additive — the generator's `kind` field is a free string and unknown kinds degrade gracefully on older consumers. |
| `layer` | One of `catalog.LAYER_ORDER`. The catalog generator validates this; the value drives bootstrap-step sequencing across capabilities. |
| `env_vars` | List of canonical environment variable names. The generated app and `.env.example` must use exactly these names. |
| `card.name` | Human-readable display name. |
| `card.description` | One-sentence neutral description — what the tool is, not why to pick it. |
| `cost_tier` | One of `free`, `fixed-monthly`, `per-call`. Drives the recipe-level `cost_profile:` aggregation. |

### Optional fields

| Field | When to set it |
|-------|----------------|
| `provides` | Use for capability dedup. Two capabilities providing `embeddings_store` are treated as substitutes (resolver picks the first declared on the recipe). |
| `requires` | List of other capability ids this one depends on. Generator validates each id resolves. E.g. `obs.langfuse` declares `requires: [relational.postgres]` because Langfuse stores its state on Postgres. |
| `bootstrap_inputs` | Free-form map of inputs this capability's `bootstrap_step` reads from its `requires:` dependencies — e.g. `{database_name: langfuse}` indicates Langfuse expects a database named `langfuse` to exist on the Postgres instance before it boots. |
| `docker` | Whenever the service can run locally in compose. Omit for purely managed services (e.g. some `host.*` and `obs.langsmith`). |
| `probe` | Name of a probe function. If the probe doesn't yet exist in agent-scaffold, leave a comment in the brief — Phase 2 fills in any gaps. |
| `bootstrap_step` | Required when post-`docker_up` initialization is needed (creating collections, topics, datasources). Omit for "compose up is sufficient" services like Redis. |
| `provisioning_time` | Coarse string (`instant`, `~10s`, `~60s`, `~5min`). Lets scaffold render progress estimates during `docker compose up + bootstrap`. |
| `est_tokens` | Coarse integer estimate of the doc's whole-file token cost. Lets a consumer budget its context window when whole-file-loading capability docs into LLM context. |
| `card.capabilities_provided` | Free-form tags an external indexer can match against (the MCP Server Card discovery convention). |
| `card.required_credentials` | Env-var names carrying secrets the consumer must prompt for. For hosted/SaaS capabilities. |
| `emit_files` | List of `{source, dest}` pairs. `source` is relative to the capability's directory; `dest` is relative to project root. Glob `**` supported. |
| `deploy_configs` | Only for `kind: host`. See below. |
| `tags` | List of lowercase tokens for hybrid-intake discovery. Convention: `card.capabilities_provided[]` + the `kind` + 1–3 descriptive tokens (e.g. `cache.redis` → `[cache, in-memory, rate-limiting, session-store]`). Consumers index on these to lazy-load only the capabilities a recipe needs. |
| `when_to_load` | One-line semantic predicate over `{recipe.capabilities, recipe.framework, recipe.runtime_mode}` (e.g. `"recipe declares cache.redis"`, `"recipe declares any vector_db.*"`). Free-form prose; consumers may treat as a hint or enforce. |

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

## Capability kinds

16 known kinds across two cohorts. The catalog's `kind:` field is a free string, so unknown values degrade gracefully (older consumers surface `unresolved`).

| Cohort | Kinds | Purpose |
|---|---|---|
| **v0.2 set** | `relational`, `cache`, `vector_db`, `queue`, `obs`, `eval`, `frontend`, `host` | Original infrastructure layers. |
| **2026-SOTA set** | `mcp`, `sandbox`, `durable`, `memory_store`, `guardrail`, `embedding`, `live_data`, `rerank` | Tool connectivity (`mcp` / `live_data`), runtime (`sandbox` / `durable`), agent-native data layer (`memory_store` / `embedding` / `rerank`), safety (`guardrail`). |

## Neutrality rule

Capability docs describe **what the tool is** and **how to wire it** — they do not editorialize choice.

- **Do** describe the tool's defining traits in one or two neutral sentences (e.g. "Tavily is a managed web-search API tuned for agent loops with snippet-ranked results and follow-up question hints").
- **Do** include `## Client integration` (Python + TypeScript snippets), `## Troubleshoot` (4-row symptom-cause-fix table), and `## See also` (cross-link to the stack/ deep-reference + getting-started screen).
- **Do not** include `## Why pick this`, `## When to swap it`, or comparative prose about other capabilities. Choice rationale belongs in [`../suggestions/<blueprints-version>/<combo>.md`](../suggestions/) — scoped to a specific pattern × primitives × modifier combination and a specific blueprints release.
- **Do not** list pricing in marketing terms. The `cost_tier:` frontmatter field is the structured cost surface; depth (concrete per-call pricing) belongs in the linked stack/ doc.

This keeps the catalog's capability layer small, machine-readable, and amenable to whole-file LLM consumption. A scaffold that loads `docs/capabilities/<kind>/<name>.md` gets exactly what it needs to provision and wire that capability — nothing about whether to pick it.

## Authoring checklist

When adding or updating a capability:

- [ ] `id` exactly matches the file path under `capabilities/`
- [ ] `kind` is one of the 16 known kinds (or a new one — additive change)
- [ ] `layer` is one of `catalog.LAYER_ORDER`
- [ ] `env_vars` are CANONICAL (no project-specific prefixes) — the generated app uses these names verbatim
- [ ] If `docker:` is set, image tag is pinned (no `:latest`)
- [ ] `card.name` + `card.description` populated (neutral one-sentence description)
- [ ] `cost_tier` set (`free` / `fixed-monthly` / `per-call`)
- [ ] `requires:` declared if this capability needs another capability up before it boots; `bootstrap_inputs:` declared if the bootstrap step reads values from the dependency
- [ ] Body has: H1 title, one-paragraph factual intro, `## Client integration` (Python + TS), `## Troubleshoot` (table), `## See also` (cross-link to stack/ + getting-started)
- [ ] Body does NOT include `## Why pick this` or `## When to swap it`
- [ ] Body stays under ~120 lines — depth lives in `stack/`; choice rationale lives in `suggestions/`

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
