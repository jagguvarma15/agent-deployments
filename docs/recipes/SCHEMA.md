# Recipe frontmatter schema

Canonical specification for the YAML frontmatter block that opens every recipe under `docs/recipes/`. This is the contract every recipe's frontmatter declares. The catalog generator ([`scripts/generate_catalog.py`](../../scripts/generate_catalog.py)) aggregates these into the top-level [`catalog.yaml`](../../catalog.yaml), which is what `agent-scaffold` (and any other downstream consumer) actually reads. See [`MANIFEST_SCHEMA.md`](../../MANIFEST_SCHEMA.md) for the catalog's own schema.

> Authoritative since: introduction of this file.
> Worked reference: [`restaurant-rebooking.md`](restaurant-rebooking.md) frontmatter lines 1–116.
> Capability schema (separate contract): [`../capabilities/README.md`](../capabilities/README.md).

## Why this exists

Until this document landed, the de facto recipe schema lived in two places — the frontmatter of `restaurant-rebooking.md` (full shape) and `customer-support-triage.md` (partial: `topology` + `roles` only). New contributors had nothing authoritative to copy; scaffold maintainers had no single reference to point at. This file is that reference.

The schema is **additive**. Consumers ignore unknown frontmatter keys per the forward-compat policy in [`../../MANIFEST_SCHEMA.md`](../../MANIFEST_SCHEMA.md). Adding fields here does not break any current consumer.

## Consumer compatibility

Every field below is passed through verbatim into the catalog's `recipes[]` block. Consumers use forward-compatible parsing (`extra: ignore`) so additive fields don't break older scaffold versions. Removing or changing the semantic of an existing field requires a `schema_version` bump in `catalog.yaml` (see [`MANIFEST_SCHEMA.md`](../../MANIFEST_SCHEMA.md)).

## Worked example

The minimum useful frontmatter for a single-topology recipe with one external service and one capability:

```yaml
---
status: Blueprint (validated)
languages: [python, typescript]
required_files:
  - Dockerfile
  - docker-compose.yml
  - .github/workflows/ci.yml
recipe_dependencies:
  python:
    fastapi: ">=0.110.0"
  typescript:
    hono: "^4.0.0"
external_services: [postgres]
capabilities: [relational.postgres]
topology: single
---
```

A multi-agent recipe with `bootstrap_config` and roles. This snippet is excerpted verbatim from [`restaurant-rebooking.md`](restaurant-rebooking.md) (the worked reference cited at the top of this file) so the example and the worked reference cannot drift:

```yaml
---
status: Blueprint (design spec)
languages: [python, typescript]
required_files:
  - Dockerfile
  - docker-compose.yml
  - tests/integration/test_event_loop.py
recipe_dependencies:
  python:
    redis: ">=5.0.0"
    fastapi: ">=0.110.0"
  typescript:
    ioredis: "^5.4.0"
    hono: "^4.0.0"
external_services: [postgres, redis, qdrant, langfuse]
capabilities:
  - cache.redis
  - relational.postgres
  - vector_db.qdrant
  - queue.redis-streams
  - obs.langfuse
bootstrap_config:
  vector_collections:
    - { name: docs, vector_size: 1536, distance: cosine }
  redis_streams:
    - { name: reservations.cancelled, maxlen: 10000, consumer_group: rebooker }
    - { name: reservations.rebooked, maxlen: 10000 }
topology: multi-agent-flat
roles:
  - name: intake
    role_kind: worker
    description: "Consume reservation-change events from Redis Streams, classify (cancel / no-show / modify), build the case envelope."
    model_hint: sonnet
    model_fallbacks: [haiku]
    cost_budget_usd_per_day: 2.00
    tools: [event_bus_consumer]
  - name: eligibility
    role_kind: router
    description: "Apply auto-rebook policy rules (tier, time window, customer history) to dispatch the case along one of three terminal paths (rebook / notify host only / decline)."
    model_hint: sonnet
    model_fallbacks: [sonnet, haiku]
    cost_budget_usd_per_day: 5.00
    tools: [policy_lookup, customer_lookup]
---
```

## Field reference

### Identity

#### `status` *(required)*

The blueprint maturity label.

- **Type:** string
- **Allowed values:** `Blueprint (validated)` · `Blueprint (design spec)`
- **Consumer:** v0.2.x (informational; used to gate "validated" vs "design spec" filters in tooling).
- **Examples:** `status: Blueprint (validated)`

Validated recipes ship a complete `## Reference Implementation` body section. Design-spec recipes either omit it or label it `## Reference Implementation (pseudocode)`.

#### `languages` *(required)*

Target language tracks the recipe provides specifications for.

- **Type:** list of strings
- **Allowed values:** `python`, `typescript`
- **Consumer:** v0.2.x (gates which language-specific generation prompts the LLM receives).
- **Examples:** `languages: [python, typescript]`

A recipe that supports only one track lists only that one.

---

### Generation contract

#### `load_list`

Structured, machine-readable companion to the prose `### Load list` H3 section every recipe carries. Tells the scaffold's context assembler exactly which docs to load, with optional per-language / per-capability predicates.

- **Type:** list of `LoadListEntry` mappings (see shape below).
- **Consumer:** v0.3+ (the structured form). v0.2.x ignores the key as unknown frontmatter, so this field is additive and safe to add to any recipe today. While the loader is rolling out, the prose `### Load list` remains the human-readable canonical view.
- **Entry shape:**
  - `path` *(required)*: relative path from the recipe to the doc. Use `../patterns/<name>.md`, `../frameworks/<id>.md`, `../cross-cutting/<topic>.md`, `../stack/<id>.md`.
  - `required` *(required, bool)*: `true` for docs the scaffold must include regardless of context budget (pattern, framework, project-layout, llm). `false` for docs that may be dropped first when the budget tightens.
  - `when` *(optional, string)*: Python-like predicate over the resolver scope `{language, framework, capabilities, topology}`. Examples: `"language == 'python'"`, `"framework == 'pydantic_ai'"`, `"capabilities contains 'obs.langfuse'"`. Absent / empty predicate means "always applicable".
- **Example:**

  ```yaml
  load_list:
    - {path: ../patterns/react.md, required: true}
    - {path: ../frameworks/pydantic-ai.md, required: true, when: "language == 'python'"}
    - {path: ../frameworks/vercel-ai-sdk.md, required: true, when: "language == 'typescript'"}
    - {path: ../cross-cutting/project-layout.md, required: true}
    - {path: ../stack/llm-claude.md, required: true}
    - {path: ../stack/api-fastapi.md, required: false, when: "language == 'python'"}
    - {path: ../cross-cutting/observability.md, required: false, when: "capabilities contains 'obs.langfuse'"}
  ```

- **Conformance:** recipes without a `load_list` block fall back to the legacy prose `### Load list` section — the loader treats both as authoritative for one release. New recipes should declare `load_list` from day one. The prose section becomes a human-readable mirror; conflicts are bugs.

#### `required_files`

Paths the LLM must emit into the generated project.

- **Type:** list of strings (project-root-relative paths)
- **Consumer:** v0.2.x (currently advisory; semantics in v0.3 are still under discussion — recipes should treat the list as "files the LLM must emit; runtime may stub-skip").
- **Examples:**
  ```yaml
  required_files:
    - Dockerfile
    - docker-compose.yml
    - .github/workflows/ci.yml
    - tests/unit/test_orchestrator.py
    - tests/integration/test_event_loop.py
    - tests/eval/test_rebooking_decisions.py
  ```

Use placeholder names (`test_<x>.py`) only if every track shares the same naming; otherwise list concrete paths.

Paths must conform to the canonical [project layout](../cross-cutting/project-layout.md) — Python recipes use `app/...` and `tests/{unit,integration,eval}/...`; TypeScript recipes use `src/...` and the same `tests/` subtree. New recipes adding paths outside that layout should justify it in their "Key files" section.

#### `recipe_dependencies`

Per-language pinned package versions the generated `pyproject.toml` / `package.json` must include.

- **Type:** map of `language → map of package → version-constraint string`
- **Consumer:** v0.2.x (threaded into dependency generation).
- **Examples:**
  ```yaml
  recipe_dependencies:
    python:
      fastapi: ">=0.110.0"
      pydantic-settings: ">=2.0.0"
      structlog: ">=24.1.0"
    typescript:
      hono: "^4.0.0"
      zod: "^3.23.0"
      pino: "^9.0.0"
  ```

Pin to minimums that the recipe body genuinely relies on. Don't enumerate transitive deps.

#### `external_services`

Legacy field — list of bare service names the recipe needs.

- **Type:** list of strings
- **Consumer:** v0.2.x (mapped to runtime probes during `agent-scaffold doctor`).
- **Examples:** `external_services: [postgres, redis, qdrant, langfuse]`

This field predates `capabilities`. Until v0.3 ships, recipes should declare **both** `external_services` (for v0.2 reach) and `capabilities` (for v0.3 reach). The two should agree: every entry in `external_services` should be backed by a capability id in `capabilities`.

---

### Capability layer (v0.3+)

#### `capabilities`

Dotted capability ids matching files under [`../capabilities/<kind>/<name>.md`](../capabilities/). The scaffold's resolver reads this list, walks each id, and threads the capability bodies into context assembly + orchestrator bootstrap.

- **Type:** list of strings (dotted `<kind>.<name>` ids)
- **Consumer:** v0.3+ (silently ignored on v0.2).
- **Allowed kinds:** `vector_db`, `cache`, `relational`, `queue`, `obs`, `eval`, `frontend`, `host` (the v0.2 cohort), plus `mcp`, `sandbox`, `durable`, `memory_store`, `guardrail`, `embedding`, `live_data`, `rerank` (the additive 2026-SOTA cohort — see [`../../MANIFEST_SCHEMA.md`](../../MANIFEST_SCHEMA.md#capability-kinds) and [`../capabilities/README.md`](../capabilities/README.md)).
- **Examples:**
  ```yaml
  capabilities:
    - cache.redis
    - relational.postgres
    - vector_db.qdrant
    - obs.langfuse
    - eval.promptfoo
    - frontend.nextjs-chat
    - host.vercel
  ```

Every id must resolve to an existing capability file. Adding a capability that doesn't have a sibling under [`../capabilities/`](../capabilities/) is a contract break — the resolver will raise.

---

### Optional advanced fields

Five additive frontmatter fields surface 2026-SOTA agent integrations that the v0.2 schema couldn't represent. They are all optional, all default to empty / null, and are ignored cleanly by older scaffold builds (via Pydantic `extra: ignore` on the catalog `RecipeEntry`). New recipes should declare any of these that apply.

The eight new capability kinds these fields reference (`mcp`, `sandbox`, `durable`, `memory_store`, `guardrail`, `embedding`, `live_data`, `rerank`) are documented in [`MANIFEST_SCHEMA.md`](../../MANIFEST_SCHEMA.md#capability-kinds).

#### `mcp_servers`

MCP (Model Context Protocol) servers the generated agent connects to. Each entry binds a recipe-local identifier to a `kind: mcp` capability id and chooses the transport.

- **Type:** list of objects.
- **Entry shape:**
  - `id` *(required, string)*: recipe-local identifier (e.g. `tavily`).
  - `capability` *(required, string)*: capability id (e.g. `mcp.tavily`).
  - `transport` *(optional, enum)*: `stdio` (default; in-process spawn) or `streamable_http` (remote endpoint).
  - `env` *(optional, map)*: per-server environment-variable hints. Use the literal string `required` as the value to mark that the credential is mandatory — scaffold's `wire_credentials` step prompts for it.
- **Consumer:** v0.3+ (additive). Older scaffold ignores the key.
- **Examples:**

  ```yaml
  mcp_servers:
    - id: tavily
      capability: mcp.tavily
      transport: streamable_http
      env: { TAVILY_API_KEY: required }
    - id: postgres
      capability: mcp.postgres
      transport: stdio
      env: { POSTGRES_URL: required }
  ```

- **Conformance:** every `capability` must resolve to a capability under `docs/capabilities/mcp/<name>.md`. Malformed transport values drop the entry with a warning.

#### `skills`

File-based skills (per Anthropic's `SKILL.md` convention) the generated project bundles. Each skill is a folder under the project's `skills/` directory containing a `SKILL.md` plus optional helper scripts.

- **Type:** list of objects.
- **Entry shape:**
  - `id` *(required, string)*: kebab-case skill identifier.
  - `path` *(required, string)*: project-root-relative path to the skill's `SKILL.md` (e.g. `skills/web-search-loop/SKILL.md`).
  - `triggers` *(optional, list of strings)*: lowercase keywords / phrases hinting when the skill applies. Used by the runtime's skill loader to score relevance.
- **Consumer:** v0.3+ (additive).
- **Examples:**

  ```yaml
  skills:
    - id: web-search-loop
      path: skills/web-search-loop/SKILL.md
      triggers: [research, "look up", investigate]
    - id: citation-formatting
      path: skills/citation-formatting/SKILL.md
      triggers: [cite, citation, "source list"]
  ```

#### `guardrails`

Capability ids of the safety layers wrapping the agent's tool-call surface. Each must match a `kind: guardrail` capability.

- **Type:** list of strings (dotted `<kind>.<name>` ids).
- **Consumer:** v0.3+ (additive).
- **Examples:**
  ```yaml
  guardrails: [guardrail.llama-guard]
  ```
- **Conformance:** every id must resolve to a capability under `docs/capabilities/guardrail/<name>.md`.

#### `sandbox`

Optional capability id for the code-execution environment LLM-emitted code runs in. Set on recipes whose agents write and execute code (code-review, claude-code-subagent, etc.).

- **Type:** string (dotted `<kind>.<name>` id) or absent.
- **Consumer:** v0.3+ (additive).
- **Examples:**
  ```yaml
  sandbox: sandbox.e2b
  ```

#### `durable_workflow`

Optional capability id for the workflow-execution engine when the agent's success criterion is long-running (multi-hour / multi-day).

- **Type:** string (dotted `<kind>.<name>` id) or absent.
- **Consumer:** v0.3+ (additive).
- **Examples:**
  ```yaml
  durable_workflow: durable.temporal
  ```

---

### `bootstrap_config`

Per-recipe inputs to the bootstrap steps declared by each capability. Top-level block, not nested under each capability declaration — keeps `capabilities:` a flat list, and bootstrap steps key on capability *kind* (the same `vector_collections` block applies whether `vector_db.qdrant`, `vector_db.pgvector`, or `vector_db.chroma` is the chosen capability).

- **Type:** map of sub-block name → sub-block content
- **Consumer:** v0.3+ (silently ignored on v0.2).

Each sub-block is documented separately below.

#### `bootstrap_config.vector_collections`

Vector collections to create after `docker compose up`. Consumed by the `bootstrap_vector_db` step shared across all `vector_db.*` capabilities.

- **Type:** list of `{ name, vector_size, distance }` objects
- **Consumer:** [`../capabilities/vector_db/qdrant.md`](../capabilities/vector_db/qdrant.md), [`../capabilities/vector_db/chroma.md`](../capabilities/vector_db/chroma.md), [`../capabilities/vector_db/pgvector.md`](../capabilities/vector_db/pgvector.md)
- **Examples:**
  ```yaml
  bootstrap_config:
    vector_collections:
      - { name: docs, vector_size: 1536, distance: cosine }
      - { name: memories, vector_size: 1536, distance: cosine }
  ```

`distance` is one of `cosine` (default), `dot`, `euclidean`. `vector_size` matches the embedding model dimension.

#### `bootstrap_config.kafka_topics`

Kafka topics to create after broker is up. Consumed by `bootstrap_kafka` (the step is shared with `queue.redis-streams` — see next sub-block).

- **Type:** list of `{ name, partitions, replication_factor? }` objects
- **Consumer:** [`../capabilities/queue/kafka.md`](../capabilities/queue/kafka.md)
- **Examples:**
  ```yaml
  bootstrap_config:
    kafka_topics:
      - { name: events.in, partitions: 3 }
      - { name: events.out, partitions: 3, replication_factor: 1 }
  ```

`replication_factor` defaults to 1 for local dev; raise for production overlays.

#### `bootstrap_config.redis_streams`

Redis Streams to declare (XADD MAXLEN + consumer-group creation) after Redis is up. Consumed by `bootstrap_kafka` (the bootstrap step name is overloaded; documented in [`../capabilities/queue/redis-streams.md`](../capabilities/queue/redis-streams.md)).

- **Type:** list of `{ name, maxlen, consumer_group? }` objects
- **Consumer:** [`../capabilities/queue/redis-streams.md`](../capabilities/queue/redis-streams.md)
- **Examples:**
  ```yaml
  bootstrap_config:
    redis_streams:
      - { name: reservations.cancelled, maxlen: 10000, consumer_group: rebooker }
      - { name: reservations.rebooked, maxlen: 10000 }
  ```

`maxlen` caps the stream length (lossy, approximate); omit `consumer_group` for streams the recipe only publishes to.

#### `bootstrap_config.langsmith`

LangSmith project to create or detect via the SDK after credentials are wired.

- **Type:** object with `project_name` key
- **Consumer:** [`../capabilities/obs/langsmith.md`](../capabilities/obs/langsmith.md)
- **Examples:**
  ```yaml
  bootstrap_config:
    langsmith:
      project_name: my-agent
  ```

If the block is omitted, the bootstrap step falls back to `manifest.project_name` (set during the scaffold's interactive flow), then `default`.

---

### Topology and roles

#### `topology`

The high-level agent shape. Drives prompt assembly and which framework templates the LLM receives.

- **Type:** string
- **Allowed values:** `single` · `chain` · `parallel` · `event-driven` · `multi-agent-flat` · `multi-agent-hierarchical`
- **Consumer:** v0.3+ (LLM context assembly).
- **Examples:** `topology: multi-agent-flat`

Single-agent recipes use `single` even when they call multiple tools.

#### `roles`

Per-agent specification for multi-agent recipes. Required when `topology` is `multi-agent-flat`, `multi-agent-hierarchical`, or `event-driven`. Optional otherwise.

- **Type:** list of objects, each:
  ```yaml
  - name: string                        # short identifier
    description: string                 # one-sentence purpose
    role_kind: supervisor | worker | router | notifier
    model_hint: opus | sonnet | haiku
    model_fallbacks: [string, ...]      # optional; ordered fallback chain
    cost_budget_usd_per_day: number     # optional; per-tenant daily cap
    tools: [string, ...]                # tool names referenced from the body's Tool Specifications
  ```
- **Consumer:** v0.3+ (`name`, `description`, `role_kind`, `model_hint`, `tools` thread into context. `model_fallbacks` and `cost_budget_usd_per_day` are runtime concerns — see cross-cutting docs below).
- **Examples:**
  ```yaml
  roles:
    - name: classifier
      description: "Classify intent into {billing, technical, account, general}."
      role_kind: supervisor
      model_hint: sonnet
      tools: []
    - name: billing-specialist
      description: "Answer billing questions; look up Stripe state."
      role_kind: worker
      model_hint: sonnet
      tools: [stripe_lookup]
  ```

##### `roles[].role_kind`

- `supervisor` — routes / delegates work to other roles.
- `worker` — executes a bounded task; receives delegation.
- `router` — pure routing decision; no tool calls of its own.
- `notifier` — terminal role that produces outbound side effects (email, SMS, webhook).

Required when `roles:` is present. Worked example: [`restaurant-rebooking.md`](restaurant-rebooking.md) frontmatter lines 60–88 (four roles spanning `worker`, `router`, and `notifier`).

##### `roles[].model_fallbacks`

Ordered fallback chain consulted on 429, 5xx, or over-budget. Each entry is a `model_hint` value.

Referenced by [`../cross-cutting/model-routing.md`](../cross-cutting/model-routing.md), which explains the runtime contract.

##### `roles[].cost_budget_usd_per_day`

Per-tenant per-day USD cap for this role's LLM spend. When exceeded, the runtime either soft-warns, hard-429s, or graceful-degrades to a cheaper model (per the recipe's chosen enforcement mode).

Referenced by [`../cross-cutting/cost-tracking.md`](../cross-cutting/cost-tracking.md), which explains the attribution and enforcement model.

---

## Required vs. recommended summary

| Field | Required? | Consumer | Note |
|-------|-----------|----------|------|
| `status` | Yes | v0.2.x | |
| `languages` | Yes | v0.2.x | |
| `load_list` | Recommended | v0.3+ | Falls back to prose `### Load list` when absent |
| `required_files` | Recommended | v0.2.x | Advisory in v0.2; possibly enforced in v0.3 |
| `recipe_dependencies` | Recommended | v0.2.x | |
| `external_services` | Recommended (transition) | v0.2.x | Mirror of `capabilities` until v0.3 ships |
| `capabilities` | Recommended | v0.3+ | Required once v0.3 ships |
| `bootstrap_config` | Optional | v0.3+ | Required if recipe uses vector_db / queue / langsmith |
| `topology` | Recommended | v0.3+ | Required for multi-agent recipes |
| `roles` | Conditional | v0.3+ | Required when `topology` is multi-agent or event-driven |
| `mcp_servers` | Optional | v0.3+ | Recipes integrating with external systems via MCP |
| `skills` | Optional | v0.3+ | Recipes bundling reusable in-context procedures |
| `guardrails` | Optional | v0.3+ | Recipes requiring safety / policy enforcement |
| `sandbox` | Conditional | v0.3+ | Required for recipes whose agents execute LLM-emitted code |
| `durable_workflow` | Optional | v0.3+ | Recipes whose success criterion spans hours/days |

## Section ordering convention

The canonical recipe section order, applicable to both validated and design-spec tiers:

```
## Composes
  ### Load list
## What it does
## Architecture
## Data Models
## API Contract
## Tool Specifications
## Prompt Specifications
## Key files
## Implementation Roadmap
## Environment & Deployment
## Test Strategy
## Eval Dataset
## Design Decisions
## Reference Implementation        ← full code for validated; "(pseudocode)" label for design-spec
```

Optional tail sections allowed where present (not required): `## Seed data`, `## Lifecycle`, `## Generation instructions`. These appear in [`restaurant-rebooking.md`](restaurant-rebooking.md) and are useful as-is.

The recipe body opens with `## Composes`; the load list (which files to feed an AI assistant) is the first H3 underneath it.

## Conformance

A recipe under `docs/recipes/*.md` is schema-conformant when:

- The first line of the file is `---` (frontmatter opens).
- `status`, `languages` are present.
- Either `external_services` or `capabilities` (preferably both during the v0.2 → v0.3 transition) is present.
- Every `capabilities:` id resolves to an existing file under `docs/capabilities/<kind>/<name>.md`.
- The body opens with `## Composes` followed by `### Load list`.
- Section order matches the canonical sequence above.

Spot-checks:

```bash
# Frontmatter exists at line 1
for f in docs/recipes/*.md; do
  [ "$(basename "$f")" = "README.md" ] && continue
  head -1 "$f" | grep -q '^---$' || echo "MISSING FRONTMATTER: $f"
done

# capabilities: ids resolve
for f in docs/recipes/*.md; do
  awk '/^capabilities:/,/^[a-z_]+:/' "$f" | grep -oE '[a-z_]+\.[a-z-]+' | while read id; do
    kind=${id%.*}; name=${id#*.}
    [ -f "docs/capabilities/$kind/$name.md" ] || echo "UNRESOLVED: $id in $f"
  done
done
```

## See also

- [`../capabilities/README.md`](../capabilities/README.md) — capability frontmatter schema (the other half of the contract surface).
- [`README.md`](README.md) — recipe catalog index.
- [`../cross-cutting/cost-tracking.md`](../cross-cutting/cost-tracking.md) — runtime contract for `roles[].cost_budget_usd_per_day`.
- [`../cross-cutting/model-routing.md`](../cross-cutting/model-routing.md) — runtime contract for `roles[].model_fallbacks`.
