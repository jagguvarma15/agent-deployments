# agents.md — how AI tools should consume this repo

This doc is written for AI tools (Claude Code, Cursor, agent-scaffold, third-party consumers) reading `agent-blueprints` programmatically. For the contributor flow (adding new entries), see [`meta/HOW_TO_ADD_AN_ENTRY.md`](meta/HOW_TO_ADD_AN_ENTRY.md).

## What this repo is

A catalog of cognitive shapes for LLM-based systems. Three cohorts (each grows as new entries are authored — read `patterns-catalog.yaml` or `taxonomy.yaml` for the live set):

| Cohort | What it is |
|---|---|
| **Patterns** | Flow shapes the agent follows (`category: agent` or `category: workflow`). |
| **Primitives** | Building blocks the agent uses orthogonally to any pattern. |
| **Modifiers** | Transformations layered on a chosen pattern. |

Picking a shape is **three orthogonal decisions**: one pattern + N primitives + N modifiers. Downstream recipes mirror this in their frontmatter (`agent_pattern: <id>`, `primitives: [...]`, `modifiers: [...]`).

## The data flow

```
taxonomy.yaml                    (cohort declarations — single source of truth)
        │
        ▼
meta/validate-metadata.js        (validates per-entry metadata.json + emits)
        │
        ▼
patterns-catalog.yaml            (canonical machine-readable catalog, schema v2)
        │
        ├──▶ meta/generate-website-data.js → website/src/data/patterns.ts
        ├──▶ meta/generate-docs.js → AUTO blocks in markdown files
        └──▶ downstream consumers (agent-deployments CI, agent-scaffold, ...)
```

**For consumers:** read `patterns-catalog.yaml` (not the source per-entry files). It's deterministic, byte-stable across runs of the generator, and pin-able by git tag.

## Reading `patterns-catalog.yaml`

The catalog's top-level keys (schema v2):

```yaml
schema_version: 2
generator_version: "2.0.0"

patterns: [...]      # flow shapes (agent + workflow, distinguished by `category`)
primitives: [...]    # building blocks the agent uses
modifiers: [...]     # transformations layered on a pattern
workflows: [...]     # DERIVED VIEW — patterns[] filtered to category=workflow
                     # (backward-compat affordance; will be removed in a future major)
compositions: [...]  # cross-cohort edges from composition/combination-matrix.md
```

Each entry carries:

```yaml
id: react                          # canonical identifier (matches directory name)
name: ReAct                        # human-readable label
category: agent                    # agent | workflow | primitive | modifier
complexity: Intermediate           # Beginner | Intermediate | Advanced
description: "..."
dir: patterns/react                # repo-root-relative source directory
tier_files:                        # which tier .md files exist (only those declared in metadata.json + present on disk)
  overview: patterns/react/overview.md
  design: patterns/react/design.md
  implementation: patterns/react/implementation.md
  evolution: patterns/react/evolution.md
  observability: patterns/react/observability.md
  cost-and-latency: patterns/react/cost-and-latency.md
evolvesFrom: [prompt-chaining]     # cross-cohort references allowed
composableWith: [memory, reflection, rag]
appliesTo: [any]                   # modifiers only — which patterns this wraps
requires: [tools]
tags: [reasoning, tool_use, loop]
costTier: medium
latencyTier: variable
extras:                            # optional companion subdirs detected on disk
  prompts: patterns/react/prompts/
  schemas: patterns/react/schemas/
  code: patterns/react/code/
```

Full schema reference: [`PATTERNS_CATALOG_SCHEMA.md`](PATTERNS_CATALOG_SCHEMA.md).

## How to walk an entry

For any entry, you can fetch the tier file content from its `tier_files` map. For example, to load the full pattern docs for `react`:

```
patterns/react/overview.md        # Tier 1: when to use, headline tradeoffs
patterns/react/design.md          # Tier 2: components, data flow, failure modes
patterns/react/implementation.md  # Tier 3: pseudocode, interfaces, testing
patterns/react/evolution.md       # how this pattern grew from a simpler shape
patterns/react/observability.md   # what to trace, key metrics
patterns/react/cost-and-latency.md  # token + latency math
```

Tier 1–3 are present for every entry. Evolution / observability / cost-and-latency are recommended but not strictly required (check `tier_files` for presence).

Optional companions (declared in `extras` when present):

- `patterns/<id>/prompts/` — example prompt templates the design doc references.
- `patterns/<id>/schemas/state.py` — canonical Pydantic v2 state model + `__init__.py`.
- `patterns/<id>/code/` — runnable framework-agnostic + per-framework implementations.

## Cohort semantics

### Patterns

A pattern is a **flow shape** with a beginning, middle, and end — a distinct control structure. Examples:

- `react`: think → act → observe loop
- `rag`: retrieve, then generate
- `routing`: classify, then dispatch
- `multi_agent`: supervisor delegates to workers
- `event_driven`: trigger from queue / stream events
- `prompt-chaining` (category=workflow): code-controlled sequential LLM calls

Picking the pattern is the agent's *shape* — one per recipe.

### Primitives

A primitive is a **building block** the agent uses inside any pattern. They're orthogonal — same primitive composes with every pattern without changing the pattern's reasoning shape. Current examples include structured tool calling, cross-session memory, and file-based discoverable procedural modules — read the live `primitives[]` block in `patterns-catalog.yaml` for the current set.

A typical recipe declares one or more primitives.

### Modifiers

A modifier **wraps** a chosen pattern with a transformation. It doesn't change the flow; it overlays a concern (gates, audit overlays, dual-LLM filters, …). Each modifier declares `appliesTo: [pattern_ids]` (or `[any]` for universal modifiers). Read the live `modifiers[]` block in `patterns-catalog.yaml` for the current set.

## Reading `compositions[]`

The `compositions[]` block lists cross-cohort relationship edges parsed from [`composition/combination-matrix.md`](composition/combination-matrix.md). Each edge:

```yaml
{a: react, b: memory, kind: natural, rationale: "Add session persistence"}
```

Kinds: `natural` (compose freely), `useful` (compose with some thought), `complex` (compose with care), `redundant` (overlapping concerns), `anti` (don't compose).

Edges are undirected and deduped — each unordered pair appears at most once with `a < b` lexicographically.

## Pinning a version

This repo cuts manual tags (no automated release). Pin by git tag for stability:

```
https://raw.githubusercontent.com/jagguvarma15/agent-blueprints/v0.2.X/patterns-catalog.yaml
```

The `main` branch is a moving target. The latest tag is the safest reference for downstream tools — see [CHANGELOG.md](CHANGELOG.md) for the release history.

## Three-repo coordination

This repo is the **cognitive** layer. Two downstream repos own the operational + execution layers:

| Repo | Owns | Reads from this repo |
|---|---|---|
| [`agent-deployments`](https://github.com/jagguvarma15/agent-deployments) | Production-shaped recipes + operational concerns (auth, rate limiting, observability, capabilities) | `patterns-catalog.yaml` at CI time, embeds the relevant blocks into its own `catalog.yaml`. |
| [`agent-scaffold`](https://github.com/jagguvarma15/agent-scaffold) | CLI that turns a recipe into a runnable project | Reads `agent-deployments`' catalog (not this one directly). |

Cognitive concerns (how the agent thinks) belong here. Operational concerns (how the agent survives production) belong in `agent-deployments`. See [`foundations/system-design-heritage.md`](foundations/system-design-heritage.md) for the boundary rationale.

## See also

- [`llms.txt`](llms.txt) — discovery file for AI tools per [llmstxt.org](https://llmstxt.org/).
- [`PATTERNS_CATALOG_SCHEMA.md`](PATTERNS_CATALOG_SCHEMA.md) — full catalog schema.
- [`taxonomy.yaml`](taxonomy.yaml) — cohort declarations.
- [`meta/HOW_TO_ADD_AN_ENTRY.md`](meta/HOW_TO_ADD_AN_ENTRY.md) — contributing new entries (separate audience).
