# Capability catalog

Capabilities are the **port-typed adapters** `agent-scaffold` composes — the verified options that bind an abstract port (see [Ports & port-typed adapters](#ports--port-typed-adapters) below). A capability (e.g. `vector_db.qdrant`, `host.vercel`) ships with everything required to provision and integrate it: the port it `implements`, the flags it `provides`, env vars, a docker-compose fragment, an orchestrator bootstrap step id, a `verification` tier, optional file templates, and optional cloud-deploy hints.

Recipes opt in by declaring `capabilities:` in their frontmatter; `agent-scaffold` resolves each id against this catalog and threads the resolved set through context assembly, the orchestrator, and the generation prompt.

This catalog is consumed by `agent-scaffold` ≥ v0.3. On older scaffold versions the `capabilities:` field is silently ignored — recipes remain backwards-compatible.

> **Machine-readable index:** This directory's contents are aggregated into the top-level [`catalog.yaml`](../../catalog.yaml). If you're building a tool that consumes this repo, read the catalog rather than walking these files directly. See [`MANIFEST_SCHEMA.md`](../../MANIFEST_SCHEMA.md).

## Ports & port-typed adapters

Capabilities are **adapters** typed to an abstract **port**. Ports are the selection axes a generator binds: the kernel IR protocols (`model`, `tools`, `memory`, `runtime`, `agents`), the cross-cutting concerns (`obs`, `eval`, `guardrail`), and the deploy axes (`framework`, `host`, `frontend`, …). They live in [`docs/ports/`](../ports/) and are aggregated into `catalog.ports[]`; each declares its `cardinality`, smart `default`, and the `kinds` that satisfy it.

Each capability declares, in frontmatter:

- `implements: {port: <id>, interface_version: <range>}` — the port it binds (the port id equals the `kind`).
- `provides: [<flag>, …]` — the **canonical capability flags** the compatibility model references (the substitution currency; `card.capabilities_provided` is human discovery copy).
- `requires` / `excludes` / `conflicts` — cross-tree feature-model edges, denormalized into `catalog.compatibility[]` (`{a, b, relation, via}`) alongside same-port `substitutes`.
- `parameters` — a JSON-Schema (+ defaults) for the adapter's tunables.
- `verification: {tier, …}` — the trust tier (`T1` = pinned + reviewed; `T2` adds CI conformance; `T3+` add signing / SBOM / SLSA).

A generator chooses a valid, verified configuration by binding each port to an adapter (respecting `cardinality`) and checking the `compatibility[]` edges.

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
kind: vector_db                      # required — one of 18 known kinds (see "Capability kinds" below)
implements: {port: vector_db, interface_version: ">=1.0"}  # required — the port this adapter binds (port == kind)
layer: data                          # required — one of catalog.LAYER_ORDER; drives bootstrap sequencing
provides: [embeddings_store]         # canonical capability flags — the compatibility-model substitution currency
requires: []                         # optional — capability ids/flags this one needs (→ catalog.compatibility[])
excludes: []                         # optional — ids/flags/ports that cannot co-occur (hard)
conflicts: []                        # optional — soft incompatibilities (consumer warns)
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
parameters: {}                       # optional — JSON-Schema (+ defaults) for the adapter's tunables
verification: {tier: T1}             # required — trust tier: T1 pinned+reviewed / T2 +CI conformance / T3+ signing
docs: |                              # short markdown block injected into the LLM context tier
  Free-form. One paragraph max — depth lives in the body below the frontmatter
  and in the linked stack/ doc.
---
```

### Required fields

| Field | Notes |
|-------|-------|
| `id` | Dotted `<kind>.<name>`. Lowercase, `_` separator inside each part allowed (`vector_db.pgvector`). Must equal the file path under `capabilities/`. |
| `kind` | One of the 18 known kinds. Adding a new kind is additive — the generator's `kind` field is a free string and unknown kinds degrade gracefully on older consumers. |
| `implements` | `{port, interface_version}` — the port this adapter binds (`port` equals `kind`). The generator validates the port exists. |
| `layer` | One of `catalog.LAYER_ORDER`. The catalog generator validates this; the value drives bootstrap-step sequencing across capabilities. |
| `env_vars` | List of canonical environment variable names. The generated app and `.env.example` must use exactly these names. |
| `card.name` | Human-readable display name. |
| `card.description` | One-sentence neutral description — what the tool is, not why to pick it. |
| `cost_tier` | One of `free`, `fixed-monthly`, `per-call`. Drives the recipe-level `cost_profile:` aggregation. |
| `verification` | `{tier}` — `T1` (pinned + reviewed), `T2` (+ CI conformance), `T3+` (+ signing / SBOM / SLSA). The pragmatic trust floor. |

### Optional fields

| Field | When to set it |
|-------|----------------|
| `provides` | **Canonical capability flags** — the substitution currency the compatibility model references (`card.capabilities_provided` is human-discovery copy). Two adapters sharing a flag are substitutes. |
| `requires` | List of other capability ids/flags this one depends on. Generator validates each id resolves; denormalized into `catalog.compatibility[]`. E.g. `obs.langfuse` declares `requires: [relational.postgres]` because Langfuse stores its state on Postgres. |
| `excludes` | Ids / flags / ports that cannot co-occur with this adapter (hard incompatibility). Denormalized into `catalog.compatibility[]`. |
| `conflicts` | Soft incompatibilities — a consumer warns rather than hard-fails. |
| `parameters` | JSON-Schema (+ defaults) for the adapter's tunables (folds ad-hoc config knobs like MCP transport, embedding dims). |
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

The catalog carries `schema_version: 1` (the YAML shape) and `contract_version: 1` (the semantic guarantees) — see the [split-version model](../../MANIFEST_SCHEMA.md#schema_version-and-contract_version-the-split-version-model). Additive fields — new optional frontmatter keys, new `kind`s, the port-typing fields above — bump **neither**: consumers parse with `extra: ignore`, so older scaffolds drop unknown keys silently. A field removal or type change bumps `schema_version`; a tightened guarantee bumps `contract_version`.

## Capability kinds

18 known kinds: two infrastructure cohorts, runtime auth, plus the `core` generation-primitive kind. The catalog's `kind:` field degrades gracefully on the consumer (unknown values surface as `unresolved`), but the **producer fails closed**: `scripts/generate_catalog.py` validates every capability's `kind` against `VALID_CAPABILITY_KINDS`, so a typo'd kind fails the catalog build rather than shipping.

| Cohort | Kinds | Purpose |
|---|---|---|
| **v0.2 set** | `relational`, `cache`, `vector_db`, `queue`, `obs`, `eval`, `frontend`, `host` | Original infrastructure layers. |
| **2026-SOTA set** | `mcp`, `sandbox`, `durable`, `memory_store`, `guardrail`, `embedding`, `live_data`, `rerank` | Tool connectivity (`mcp` / `live_data`), runtime (`sandbox` / `durable`), agent-native data layer (`memory_store` / `embedding` / `rerank`), safety (`guardrail`). |
| **Runtime auth** | `auth` | Runtime API-key bootstrap (`auth.key-bootstrap`) — captures the agent's own provider key from the first chat turn instead of an env var. |
| **Core generation primitives** | `core` | Emitted project structure — spec, owned prompts, schema I/O, tool registry, step-log, tracing — seeded by the scaffold's tier presets. Not provisioned infra. |

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
- [ ] `kind` is one of the 18 known kinds (or a new one — additive change)
- [ ] `implements: {port}` set — the port id equals the `kind`
- [ ] `layer` is one of `catalog.LAYER_ORDER`
- [ ] `env_vars` are CANONICAL (no project-specific prefixes) — the generated app uses these names verbatim
- [ ] If `docker:` is set, image tag is pinned (no `:latest`)
- [ ] `card.name` + `card.description` populated (neutral one-sentence description)
- [ ] `cost_tier` set (`free` / `fixed-monthly` / `per-call`)
- [ ] `verification: {tier}` set (`T1` minimum — pinned + reviewed)
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
