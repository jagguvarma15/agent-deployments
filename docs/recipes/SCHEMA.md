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

### Composition (the three orthogonal decisions)

Designing an agent is three picks: one pattern + N primitives + N modifiers. Every recipe declares its three picks in frontmatter; the catalog generator validates each id against the embedded blueprints catalog and refuses to emit a catalog with an unresolved reference.

#### `agent_pattern` *(required)*

The cognitive flow shape this recipe implements. References `catalog.patterns[].id` (which includes both agent patterns and workflow patterns via the `category` field).

- **Type:** string
- **Allowed values:** any id in `catalog.patterns[]` — currently `agentic_rag`, `event_driven`, `evaluator-optimizer`, `long_horizon`, `multi_agent`, `orchestrator-worker`, `parallel-calls`, `plan_and_execute`, `prompt-chaining`, `rag`, `react`, `reflection`, `routing`, `saga`.
- **Consumer:** v0.3+ (drives prompt assembly + framework template selection).
- **Examples:** `agent_pattern: react` · `agent_pattern: routing` · `agent_pattern: event_driven`

Use the canonical underscore form for ids that contain a word break (`event_driven`, `plan_and_execute`, `multi_agent`). Workflow-category ids use hyphens (`prompt-chaining`, `parallel-calls`).

#### `primitives`

Orthogonal building blocks the recipe uses across the chosen pattern. References `catalog.primitives[].id`.

- **Type:** list of strings (may be empty or omitted)
- **Allowed values:** any id in `catalog.primitives[]` — currently `memory`, `tool_use`, `skills`, `sub_agents`.
- **Consumer:** v0.3+ (each primitive's overview is added to the generation context).
- **Examples:**
  ```yaml
  primitives: [tool_use, memory]
  ```

Almost every recipe declares `tool_use` (most agents call at least one tool). Use `memory` for recipes whose value depends on retention across sessions; `sub_agents` for delegating supervisor/worker patterns; `skills` for recipes that ship `SKILL.md`-format reusable procedures.

#### `modifiers`

Transformations layered on the chosen pattern. References `catalog.modifiers[].id`.

- **Type:** list of strings (may be empty or omitted)
- **Allowed values:** any id in `catalog.modifiers[]` — currently `guardrails`, `human_in_the_loop`.
- **Consumer:** v0.3+ (each modifier's overview is added to the generation context).
- **Examples:**
  ```yaml
  modifiers: [human_in_the_loop]
  ```

Add `human_in_the_loop` when the recipe's success criterion requires an approval gate before a tool call commits (refunds, code merges, payment authorization). Add `guardrails` when the recipe's input/output surface is exposed to untrusted users and an indirect-prompt-injection defense is mandatory.

---

### Generation contract

#### `load_list`

Structured, machine-readable companion to the prose `### Load list` H3 section every recipe carries. Tells the scaffold's context assembler exactly which docs to load, with optional per-language / per-capability predicates.

- **Type:** list of `LoadListEntry` mappings (see shape below).
- **Consumer:** v0.3+ (the structured form). v0.2.x ignores the key as unknown frontmatter, so this field is additive and safe to add to any recipe today. While the loader is rolling out, the prose `### Load list` remains the human-readable canonical view.
- **Entry shape:**
  - `path` *(required)*: relative path from the recipe to the doc. Use `../patterns/<name>.md`, `../frameworks/<id>.md`, `../cross-cutting/<topic>.md`, `../stack/<id>.md`.
  - `required` *(required, bool)*: `true` for docs the scaffold must include regardless of context budget (pattern, framework, project-layout, llm). `false` for docs that may be dropped first when the budget tightens.
  - `when` *(optional, string)*: predicate over the resolver scope `{language, framework, capabilities, topology}`. Absent / empty means "always applicable". This is **not** free-form Python — exactly two forms are valid:

    ```ebnf
    predicate    = scalar_eq | contains ;
    scalar_eq    = ( "language" | "framework" | "topology" ) , "==" , quoted_value ;
    contains     = "capabilities" , "contains" , quoted_value ;
    quoted_value = "'" , value_chars , "'" | '"' , value_chars , '"' ;
    value_chars  = any characters except quote marks (non-empty) ;
    ```

    Whitespace around tokens is insignificant. Examples: `"language == 'python'"`, `"framework == 'pydantic_ai'"`, `"topology == 'single'"`, `"capabilities contains 'obs.langfuse'"`. There is no negation, no `and`/`or`, no other left-hand attributes — split a doc into multiple entries instead.

    **Enforcement is asymmetric by design.** The catalog generator fails *closed*: any predicate outside this grammar (and any `capabilities contains` id with no `docs/capabilities/` entry) hard-fails the build, so a typo never ships. Consumers evaluate *fail-open*: a predicate they can't parse loads the doc anyway (with a warning), so a newer grammar never silently drops a required doc from an older consumer's context. The generator's regexes mirror the scaffold's `context.evaluate_load_list_predicate` exactly — change them together.
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

##### `load_list[].cache_tier` *(optional, generator-defaulted)*

Per-entry hint telling consumers which Anthropic `cache_control` tier each doc belongs in. The generator computes a path-based default when the entry doesn't author one; authored values win after enum validation.

- **Type:** enum `hot` | `warm` | `dynamic`.
- **Consumer:** the consumer assembling the prompt with cache breakpoints (typically the scaffold CLI or any other AI tool that reads the catalog).
- **Path-based defaults:** `vendored/blueprints/**`, `frameworks/**`, `stack/**`, and `cross-cutting/project-layout.md` → `hot`; other `cross-cutting/**` + `capabilities/**` + the recipe body → `warm`; everything else → `dynamic`. See [`MANIFEST_SCHEMA.md`](../../MANIFEST_SCHEMA.md#recipesload_listcache_tier) for the full mapping including the Anthropic TTL table.
- **Authoring guidance:** authors rarely need to override the default. Set it explicitly when:
  - A `cross-cutting/` doc is *foundational* for the recipe and you want it in the 1h hot cache.
  - A `stack/` doc is *experimental* and you want it in the 5m warm tier instead.
  - A `capabilities/` doc is *load-bearing* enough that 1h hot caching saves more than the 2.0× write cost.
- **Consumer contract:** every emitted `load_list[]` entry carries a `cache_tier` value. Consumers can rely on the field being present.
- **4-breakpoint budget:** Anthropic allows at most 4 `cache_control` breakpoints per request. Canonical placement: hot/warm boundary, warm/dynamic boundary, last assistant turn (conversational recipes), plus one spare. If the recipe's `load_list` implies more, the consumer collapses adjacent same-tier entries.

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

### Local-bringup contract

The five fields below let a consumer (scaffold CLI, AI tool) produce a working local project from a recipe spec without inventing domain logic. Every required field is enforced by the catalog generator.

#### `runtime_modes` *(required)*

Named runtime modes the recipe supports, each declaring concrete capability swaps applied when the consumer selects that mode.

- **Type:** map of `<mode-name>` → `{description: string, swaps: map<from-id, to-id>}`
- **Consumer:** v0.3+ (drives capability resolution + .env generation).
- **Required keys:** at minimum a `default` mode with `swaps: {}`.
- **Examples:**
  ```yaml
  runtime_modes:
    default:
      description: "Anthropic Claude + SaaS rerank/search + local Postgres/Redis/Langfuse."
      swaps: {}
    local_only:
      description: "Self-hosted vLLM + BGE rerank + SearXNG. No SaaS keys needed."
      swaps:
        stack/llm-claude: stack/llm-local-vllm
        rerank.cohere: rerank.bge-local
        live_data.tavily: live_data.searxng
    hybrid:
      description: "Default + Langsmith for hosted observability."
      swaps:
        obs.langfuse: obs.langsmith
  ```

The catalog generator validates each swap's `from` and `to` ids resolve to a capability id or `docs/stack/<x>.md` path-style reference.

##### `runtime_modes[<mode>].context_budget` *(optional)*

Per-mode context-window envelope. Lets the consumer (or runtime) bound prompt assembly against the mode's chosen model class.

- **Type:** object with `input_max` (positive int) and `output_max` (positive int).
- **Consumer:** generator validates types; consumers interpret magnitudes against their model.
- **Recommended values:**
  - `default` mode (Claude Sonnet 4.6 envelope): `{input_max: 80000, output_max: 8000}`.
  - `local_only` mode (Llama 3.1 8B-equivalent): `{input_max: 32000, output_max: 4000}`.
  - `local_only` mode (Llama 3.1 70B-equivalent on vLLM): `{input_max: 80000, output_max: 8000}`.
- **Example:**
  ```yaml
  runtime_modes:
    default:
      description: "Anthropic Claude — Sonnet across the loop."
      swaps: {}
      context_budget: {input_max: 80000, output_max: 8000}
    local_only:
      description: "Self-hosted vLLM serving Llama 3.1 8B."
      swaps:
        stack/llm-claude: stack/llm-local-vllm
      context_budget: {input_max: 32000, output_max: 4000}
  ```

When `context_budget` is absent, consumers fall back to their own per-model defaults rather than assume "unlimited."

#### `smoke_test` *(required)*

Shell-string commands the consumer runs after `docker compose up` + bootstrap to verify the recipe is locally healthy.

- **Type:** object with three required keys:
  - `ready` *(string)*: shell command (`curl -sf`, `pg_isready`, etc.) that exits 0 when the app's HTTP / health surface is ready.
  - `exercise` *(string)*: shell command that submits one representative agent request.
  - `assert_jq` *(string)*: a `jq` expression evaluated against `exercise`'s stdout that must evaluate to a truthy value (`true`, non-empty string, non-zero number).
- **Consumer:** v0.3+ (`make smoke` target runs these in order).
- **Examples:**
  ```yaml
  smoke_test:
    ready: "curl -sf http://localhost:8000/health"
    exercise: |
      curl -sf -X POST http://localhost:8000/research \
        -H 'content-type: application/json' \
        -d '{"question":"smoke test","max_steps":2}'
    assert_jq: '.answer | length > 0'
  ```

The generator validates all three keys are present.

#### `cost_profile` *(required)*

Per-recipe cost surface the consumer renders before running.

- **Type:** object with:
  - `tier` *(required, enum)*: `free` | `low` | `medium` | `high`.
  - `sources` *(required, list of strings)*: provider names that incur cost (e.g. `[anthropic, tavily]`).
  - `typical_run_usd` *(optional, number)*: an order-of-magnitude estimate of one representative agent invocation.
- **Consumer:** v0.3+ (rendered in the wizard preview).
- **Examples:**
  ```yaml
  cost_profile:
    tier: low
    sources: [anthropic, tavily]
    typical_run_usd: 0.02
  ```

`tier: free` is reserved for recipes whose `default` runtime_mode has `cost_profile.sources: []` (all-local stack). The generator validates `tier` and `sources`.

#### `model_recommendation` *(optional)*

The recommended LLM model id per role for multi-agent recipes, or a single string for single-agent recipes.

- **Type:** string (single-agent) or map `<role-name>` → `<model-id>` (multi-agent).
- **Consumer:** v0.3+ (passed to the generation prompt).
- **Examples:**
  ```yaml
  # Single-agent recipe
  model_recommendation: claude-sonnet-4-6

  # Multi-agent recipe
  model_recommendation:
    intake: claude-haiku-4-5
    eligibility: claude-sonnet-4-6
    rebooker: claude-sonnet-4-6
    notifier: claude-haiku-4-5
  ```

When set, the recipe's `roles[].model_hint` becomes informational (the recommendation wins).

#### `env_overrides` *(optional)*

Recipe-specific env-var defaults or additions that override / augment the generator's auto-derived `env_contract`.

- **Type:** map `<VAR_NAME>` → `<default-value>`.
- **Consumer:** v0.3+ (merged into the emitted `.env.example`).
- **Examples:**
  ```yaml
  env_overrides:
    APP_PORT: 8000
    MAX_STEPS: 5
    LOG_LEVEL: info
  ```

Used for app-level vars the capabilities don't own (`APP_PORT`, `MAX_STEPS`) and for pinning capability defaults the recipe wants different from the capability's default.

#### `env_contract` *(auto-derived, do not author)*

The catalog generator emits this block per recipe by walking each `capabilities[]`, collecting every capability's `env_vars`, deduping, and annotating with source-capability + `env_overrides` defaults. Authors must NOT include this in their frontmatter — the generator raises if it's hand-authored.

Consumers read `catalog.recipes[].env_contract` to render the canonical `.env.example` without re-walking the capability set.

#### `est_tokens` *(recommended)*

Coarse estimate of the recipe's whole-file token cost. Lets a consumer budget its context window.

- **Type:** integer.
- **Consumer:** v0.3+ (informational; surfaces in the wizard preview).
- **Example:** `est_tokens: 4200`

#### `acceptance_contracts` *(mandatory for validated recipes)*

Machine-checkable contracts the consumer validates the generated project against after `docker compose up` + smoke pass. Lets external tooling (CI smoke jobs, scaffold doctor) answer "did the generated project actually conform?" without re-reading the recipe body.

- **Type:** mapping with four sub-blocks. Each sub-block has its own shape (see below). The generator validates structure + reference resolution when the block is present.
- **Requiredness:** for recipes with `status: Blueprint (validated)`, the block **and all four sub-keys** must be declared — an explicit empty list (`required_compose_services: []`) is fine, silence is a hard generator error. Design-spec recipes get a soft warning when the block is missing (it becomes mandatory the moment the recipe flips to validated). Additionally, every `required_env` entry with `source: capability:<id>` must appear in the recipe's derived `env_contract` — a contract promising an env var no capability declares is unsatisfiable by consumers and fails the build.
- **Consumer:** v0.3+ (additive; ignored by older builds via Pydantic `extra: ignore`).
- **Sub-blocks:**

  ##### `acceptance_contracts.http_endpoints`

  Endpoints the generated project must expose. Generator requires each entry's `path` to be a string starting with `/`.

  ```yaml
  http_endpoints:
    - {path: /health, method: GET, status: 200}
    - {path: /research, method: POST, status: 200, response_schema_ref: "#/data/ResearchResponse"}
  ```

  Include `/health` even for event-driven recipes (it's the readiness probe).

  ##### `acceptance_contracts.required_env`

  Env-vars that must be set before the project boots. `source: prompted` means the consumer asks the user; `source: capability:<id>` means the value comes from the named capability and the id must resolve.

  ```yaml
  required_env:
    - {name: ANTHROPIC_API_KEY, source: prompted}
    - {name: DATABASE_URL,      source: capability:relational.postgres}
  ```

  ##### `acceptance_contracts.required_compose_services`

  Docker-compose service names that must be present and healthy. Generator requires every entry to match some capability's `docker_service`.

  ```yaml
  required_compose_services: [postgres, redis, langfuse]
  ```

  ##### `acceptance_contracts.smoke_assertions`

  Jq expressions evaluated against `smoke_test.exercise`'s stdout (or another named stream). At least one assertion is conventional — for event-driven recipes (no HTTP), it's where the bulk of the contract lives.

  ```yaml
  smoke_assertions:
    - {jq: ".answer | length > 0", against: smoke_test.exercise.stdout}
  ```

- **Worked example:**
  ```yaml
  acceptance_contracts:
    http_endpoints:
      - {path: /health, method: GET, status: 200}
      - {path: /research, method: POST, status: 200, response_schema_ref: "#/data/ResearchResponse"}
    required_env:
      - {name: ANTHROPIC_API_KEY, source: prompted}
      - {name: DATABASE_URL, source: capability:relational.postgres}
    required_compose_services: [postgres, langfuse]
    smoke_assertions:
      - {jq: ".answer | length > 0", against: smoke_test.exercise.stdout}
  ```

#### Forward note: `### Generation prompt` H3

A future content scope will populate a `### Generation prompt` H3 section in every recipe's body, placed immediately after `## Composes` and before `## What it does`. The section will hold a copy-pasteable prompt scaffold-CLI users can drop into Claude Code or Cursor to bootstrap the recipe before agent-scaffold ships. It's a body section, not a frontmatter field — this SCHEMA.md notes its existence so authors don't accidentally overwrite it during refactors.

---

## Required vs. recommended summary

| Field | Required? | Consumer | Note |
|-------|-----------|----------|------|
| `status` | Yes | v0.2.x | |
| `languages` | Yes | v0.2.x | |
| `agent_pattern` | Yes | v0.3+ | Must resolve to a `catalog.patterns[].id` |
| `primitives` | Recommended | v0.3+ | Empty list allowed; ids must resolve to `catalog.primitives[]` |
| `modifiers` | Optional | v0.3+ | Ids must resolve to `catalog.modifiers[]` |
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
| `runtime_modes` | Yes | v0.3+ | At minimum a `default` mode; each swap's ids must resolve |
| `smoke_test` | Yes | v0.3+ | All three keys (`ready`, `exercise`, `assert_jq`) required |
| `cost_profile` | Yes | v0.3+ | `tier` + `sources` required |
| `model_recommendation` | Recommended | v0.3+ | String (single-agent) or per-role map (multi-agent) |
| `env_overrides` | Optional | v0.3+ | Merged into the emitted `.env.example` on top of `env_contract` |
| `env_contract` | Auto-derived | v0.3+ | Generator emits; do NOT author |
| `est_tokens` | Recommended | v0.3+ | Whole-file token estimate |
| `load_list[].cache_tier` | Auto-defaulted | v0.3+ | Enum `hot \| warm \| dynamic`; generator computes from path when not authored |
| `runtime_modes[<mode>].context_budget` | Optional | v0.3+ | `{input_max, output_max}` positive ints per mode |
| `acceptance_contracts` | Optional | v0.3+ | Machine-checkable contracts for the generated project |

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
- `status`, `languages`, `agent_pattern` are present.
- Either `external_services` or `capabilities` (preferably both during the v0.2 → v0.3 transition) is present.
- Every `capabilities:` id resolves to an existing file under `docs/capabilities/<kind>/<name>.md`.
- Every `agent_pattern:` / `primitives[]` / `modifiers[]` id resolves to a `catalog.{patterns,primitives,modifiers}[].id`.
- The body opens with `## Composes` followed by `### Load list`.
- Section order matches the canonical sequence above.

Spot-checks:

```bash
# Frontmatter exists at line 1 + agent_pattern is declared
for f in docs/recipes/*.md; do
  base=$(basename "$f")
  [ "$base" = "README.md" ] && continue
  [ "$base" = "SCHEMA.md" ] && continue
  head -1 "$f" | grep -q '^---$' || echo "MISSING FRONTMATTER: $f"
  grep -q '^agent_pattern:' "$f" || echo "MISSING agent_pattern: $f"
done

# capabilities: ids resolve
for f in docs/recipes/*.md; do
  awk '/^capabilities:/,/^[a-z_]+:/' "$f" | grep -oE '[a-z_]+\.[a-z-]+' | while read id; do
    kind=${id%.*}; name=${id#*.}
    [ -f "docs/capabilities/$kind/$name.md" ] || echo "UNRESOLVED: $id in $f"
  done
done

# Full id resolution (agent_pattern, primitives, modifiers, capabilities) is
# enforced by `uv run scripts/generate_catalog.py` — the generator refuses
# to emit a catalog if anything fails to resolve.
```

## See also

- [`../capabilities/README.md`](../capabilities/README.md) — capability frontmatter schema (the other half of the contract surface).
- [`README.md`](README.md) — recipe catalog index.
- [`../cross-cutting/cost-tracking.md`](../cross-cutting/cost-tracking.md) — runtime contract for `roles[].cost_budget_usd_per_day`.
- [`../cross-cutting/model-routing.md`](../cross-cutting/model-routing.md) — runtime contract for `roles[].model_fallbacks`.
