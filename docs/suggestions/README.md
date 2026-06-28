# Suggestions cohort

Per-combo stack recommendations for the current `agent-blueprints` release. One markdown per `(pattern × primitives × modifiers)` combination; all combo files for the same blueprints version live under `docs/suggestions/<blueprints-version>/`.

## Why this exists

The capability docs are deliberately **neutral** — each describes what a tool is and how to wire it, never why to pick one over another. Choice guidance belongs here, where it's scoped to the specific upstream blueprints release the suggestions were authored against.

Consumers (scaffold CLIs, AI tools) read the catalog's `suggestions:` block to find the right combo file for a recipe's `agent_pattern` + `primitives` + `modifiers`, then load that file to learn which capability ids the maintainers currently recommend filling each stack slot with.

## Layout

```
docs/suggestions/
├── README.md                   # this file
└── <blueprints-version>/       # exactly one version dir at any time
    ├── react+tool_use.md
    ├── react+tool_use+memory.md
    ├── routing+tool_use.md
    ├── rag.md
    └── …
```

The `<blueprints-version>/` directory name matches the upstream version pinned in [`../../reference/blueprints/patterns-catalog.yaml`](../../reference/blueprints/patterns-catalog.yaml) (e.g. `7420e28`). **Only one version directory exists on disk at any time.** The sync workflow ([`.github/workflows/sync-blueprints.yml`](../../.github/workflows/sync-blueprints.yml)) deletes the prior version directory when bumping the upstream pin; the new version starts empty until authors land its combo files. The catalog generator raises if more than one `<version>/` directory exists.

This keeps the suggestions surface honest: a consumer reading `catalog.suggestions.blueprints_version` knows which upstream taxonomy the recommendations were validated against, and there is no ambiguity about which directory's contents are current.

## Combo file naming

The file name encodes the combo using `+` as separator:

```
<pattern>+<primitive-1>+<primitive-2>+…+<modifier-1>+….md
```

- Patterns and primitives use their canonical ids (underscored where applicable: `event_driven`, `tool_use`, `human_in_the_loop`).
- Order: pattern first, primitives next in alphabetical order, modifiers last in alphabetical order.
- A combo with zero primitives and zero modifiers uses just the pattern name: `rag.md`, `prompt-chaining.md`.

Examples:

| Combo | File |
|---|---|
| react + tool_use | `react+tool_use.md` |
| react + tool_use + memory | `react+tool_use+memory.md` |
| react + tool_use + sub_agents + skills | `react+sub_agents+skills+tool_use.md` (primitives alphabetical) |
| event_driven + tool_use + human_in_the_loop | `event_driven+tool_use+human_in_the_loop.md` |
| rag (no primitives, no modifiers) | `rag.md` |

The catalog generator enforces ordering via parse.

## Combo file frontmatter

```yaml
---
blueprints_version: v0.1.0
applies_to:
  pattern: react
  primitives: [tool_use]
  modifiers: []
recommends:
  framework: pydantic_ai           # or vercel_ai_sdk for TS-first recipes
  llm: stack/llm-claude            # path-style reference to a stack doc or capability id
  api_layer: stack/api-fastapi
  relational: relational.postgres
  cache: cache.redis
  vector_db: null                  # explicit null when not applicable to this combo
  retrieval: null
  queue: null
  obs: obs.langfuse
  eval: eval.promptfoo
  mcp_servers: [mcp.tavily]
  sandbox: null
  durable: null
  memory_store: null
  guardrail: null
  embedding: null
  rerank: null
local_only_swaps:                  # capability swaps for the `local_only` runtime_mode
  - {from: stack/llm-claude, to: stack/llm-local-ollama}
est_tokens: 600
---
```

### Required fields

| Field | Type | Notes |
|---|---|---|
| `blueprints_version` | string | Must match the directory name and the version derived from `reference/blueprints/patterns-catalog.yaml`. |
| `applies_to.pattern` | string | One canonical `catalog.patterns[].id`. |
| `applies_to.primitives` | list of strings | Zero or more `catalog.primitives[].id`. |
| `applies_to.modifiers` | list of strings | Zero or more `catalog.modifiers[].id`. |
| `recommends` | map | At minimum: `framework` + `llm`. Other slots may be `null` when not applicable to this combo. |

### Optional fields

| Field | Type | Notes |
|---|---|---|
| `local_only_swaps` | list of `{from, to}` | Capability swaps applied when a recipe is run in `local_only` runtime_mode. Each `from`/`to` is a capability id or stack-doc path-style reference. |
| `est_tokens` | int | Coarse estimate of the whole-file token cost. |

The catalog generator validates: `blueprints_version` matches the dir, every `recommends:` value resolves to a capability id or `docs/stack/<x>.md` path or is `null`, every `local_only_swaps[].from`/`to` resolves.

## Body shape

Keep it short. ~30-50 lines per combo file. Structure:

```markdown
# Stack suggestion: <Pattern> + <Primitives>

Short paragraph naming the use cases this combo fits.

## Recommended picks (default mode)

| Slot | Pick | Why |
|---|---|---|
| Framework | … | one sentence on the fit |
| LLM | … | … |
| … | … | … |

## Local-only swaps

Bullet list of the swaps the `local_only` runtime_mode applies, with one sentence each on the trade-off.

## See also

- [`<recipe>`](../../recipes/<recipe>.md) and other recipes that ship this combo
- [`patterns/<pattern>/overview.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/patterns/<pattern>/overview.md)
```

The "Why" column is descriptive (this fits because the framework's tool-calling surface lines up with the pattern), not comparative (this is better than X). Capability docs stay neutral; combo files explain pick rationale in this scoped way.

## How the catalog generator reads this

For each `docs/suggestions/<version>/*.md`:

1. Parse frontmatter; validate as above.
2. Emit one entry into `catalog.suggestions.combos[]` with `applies_to`, `path`, and the `recommends` map (resolved to ids/paths).
3. Set `catalog.suggestions.blueprints_version` from the directory name (validated to match every combo file's frontmatter).

If `docs/suggestions/` contains more than one `<version>/` directory, the generator raises. The sync workflow's purge step is what enforces the single-version invariant in CI.

## Authoring workflow

When `agent-blueprints` cuts a new release and the sync workflow purges the prior `docs/suggestions/<old>/` directory:

1. The catalog's `suggestions:` block becomes empty (`combos: []`).
2. Authors land new combo files under the new `docs/suggestions/<new-version>/` directory, one per combo currently shipped by the 11 recipes.
3. Each PR's drift CI gates the per-combo schema.

There is no requirement to re-author every combo for every blueprints release — old combos that still apply to the new taxonomy can be copied forward verbatim with only the `blueprints_version:` field updated.

## See also

- [`../recipes/SCHEMA.md`](../recipes/SCHEMA.md) — recipe frontmatter contract (recipes declare `agent_pattern` + `primitives` + `modifiers` that combo files key on).
- [`../capabilities/README.md`](../capabilities/README.md) — capability frontmatter contract (`recommends:` values resolve here).
- [`../../MANIFEST_SCHEMA.md`](../../MANIFEST_SCHEMA.md) — top-level `catalog.suggestions:` block schema.
- [`foundations/choosing-a-pattern.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/foundations/choosing-a-pattern.md) — upstream picker that produces the pattern + primitives + modifiers combination this cohort recommends a stack for.
