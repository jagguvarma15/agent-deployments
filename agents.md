# agents.md — programmatic consumption guide

If you're an AI tool (Claude Code, Cursor, agent-scaffold, …) reading this repo, start here. For humans, the entry point is [`README.md`](README.md).

## Role in the pipeline

```
agent-blueprints   →   agent-deployments   →   agent-scaffold
(cognitive shape)      (stack decision)        (code generation)
```

This is the **stack-decision** layer. After you've picked a cognitive pattern from agent-blueprints, the next decision is what to run it on. Every recipe here answers that: pattern + framework + infrastructure capabilities + cross-cutting concerns, fully spec'd.

## The contract you parse

[`catalog.yaml`](catalog.yaml) at this repo's root. One URL, one file. Everything else (recipes, capabilities, frameworks, the embedded blueprints catalog) is reachable through it.

| Top-level key | Shape | Use it to |
|---|---|---|
| `schema_version` | int | Refuse to parse if higher than your declared max. |
| `blueprints` | object | Resolve recipe-body references to upstream blueprint doc URLs. |
| `patterns[]` / `primitives[]` / `modifiers[]` | embedded from upstream | Validate recipe id references. |
| `workflows[]` | derived view | Compat for older consumers; same ids as patterns where `category=workflow`. |
| `compositions[]` | embedded from upstream | Discover allowed pattern combinations. |
| `recipes[]` | this repo | The agents you can scaffold. |
| `capabilities[]` | this repo | Infrastructure pieces a recipe needs. |
| `frameworks[]` / `stack[]` / `cross_cutting_docs[]` | this repo | Doc paths to include in context. |
| `pattern_docs[]` / `primitive_docs[]` / `modifier_docs[]` | upstream overview URLs | Alias resolver target. |
| `aliases` / `cross_cutting` | maps | Prose-token → path lookup. |
| `non_recipe_stems` / `min_alias_length` | hints | Filtering knobs. |

Older scaffold versions parse with `extra: ignore` — any unknown top-level key is silently dropped. New fields are additive at the current `schema_version: 1`.

## Loading a recipe (the canonical algorithm)

1. Read the recipe's YAML frontmatter (block delimited by `---` at file start).
2. Resolve **`agent_pattern:`** against `catalog.patterns[].id`. Must exist.
3. Resolve each id in **`primitives:`** against `catalog.primitives[].id`. All must exist.
4. Resolve each id in **`modifiers:`** against `catalog.modifiers[].id`. All must exist.
5. Resolve each id in **`capabilities:`** against `catalog.capabilities[].id`. All must exist.
6. Walk **`load_list:`** entries, applying the per-entry `when:` predicate against `{language, framework, capabilities, topology}`. Concatenate the surviving docs into your generation context, in declared order.
7. For prose mentions inside the recipe body that don't appear in `load_list`, fall through to `catalog.aliases` (length ≥ `min_alias_length`) then `catalog.cross_cutting`.

The catalog generator validates steps 2–5 at build time — if your fetched catalog parses cleanly, every id in every recipe resolves. You can trust the references without re-checking.

## Bringing a recipe up locally

After generation, a consumer that wants `docker compose up && make smoke` to pass uses these catalog reads:

1. **Pick a runtime mode.** Read `catalog.recipes[].runtime_modes` for the target recipe; pick one (`default` always exists; `local_only` and `hybrid` may also be present). Apply the mode's `swaps:` map to the recipe's `capabilities[]` before going further.
2. **Look up combo recommendations.** Read `catalog.suggestions.combos[]`; find the entry whose `applies_to` matches `(agent_pattern, primitives, modifiers)`. Its `recommends:` map names the canonical framework + stack-doc picks for this combo at the current upstream blueprints version.
3. **Sequence bootstrap by layer.** Read `catalog.LAYER_ORDER` (an ordered list). For each layer, gather the recipe's capabilities whose `layer:` matches; bring them up via Compose; run each capability's `bootstrap_step` in declaration order, passing the values declared in `bootstrap_inputs:` from any `requires:` dependencies.
4. **Render `.env.example`.** Read `catalog.recipes[].env_contract` (auto-derived by the generator). Each entry carries `{name, source_capability, default?}`. Merge `catalog.recipes[].env_overrides` on top (recipe wins over capability default). Emit the canonical block.
5. **Surface cost preview.** Read `catalog.recipes[].cost_profile` (`tier`, `sources[]`, `typical_run_usd?`). Render before the user commits to generation.
6. **Run the smoke test.** Read `catalog.recipes[].smoke_test` (`{ready, exercise, assert_jq}`). Run `ready` until exit 0 (with timeout). Then run `exercise`, capture stdout. Then evaluate `assert_jq` against that stdout; succeed if truthy.

Steps 1-6 use only fields validated by the catalog generator. If the catalog parses, the contract holds.

## The three-decision composition

Every recipe declares (or will declare) three orthogonal fields:

```yaml
agent_pattern: react              # one id from catalog.patterns[]
primitives: [tool_use, memory]    # zero or more from catalog.primitives[]
modifiers: [human_in_the_loop]    # zero or more from catalog.modifiers[]
```

This mirrors the upstream taxonomy in agent-blueprints. The picker is described in [`foundations/choosing-a-pattern.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/foundations/choosing-a-pattern.md).

## Capability kinds

Catalog `capabilities[].kind` is a free string. The known kinds today, by cohort:

- **v0.2 set:** `vector_db`, `cache`, `relational`, `queue`, `obs`, `eval`, `frontend`, `host`.
- **2026-SOTA set:** `mcp`, `sandbox`, `durable`, `memory_store`, `guardrail`, `embedding`, `live_data`, `rerank`.

Unknown kinds should degrade gracefully (surface as `unresolved` rather than raise). See [`MANIFEST_SCHEMA.md`](MANIFEST_SCHEMA.md#capability-kinds).

## Pinning convention

Track tagged releases of this repo. The catalog is republished on every release. Between releases, you can fetch the live `catalog.yaml` from `main` if your tool needs the newest content, but production consumers should pin.

The blueprints catalog embedded here is generated from a SHA-pinned reference copy at `reference/blueprints/patterns-catalog.yaml`, refreshed on each upstream release. This repo's release cadence drives the freshness of the blueprints content downstream consumers see.

## Reading further

- [`STRUCTURE.md`](STRUCTURE.md) — directory map.
- [`MANIFEST_SCHEMA.md`](MANIFEST_SCHEMA.md) — full catalog field reference.
- [`docs/recipes/SCHEMA.md`](docs/recipes/SCHEMA.md) — recipe authoring contract.
- [`docs/capabilities/README.md`](docs/capabilities/README.md) — capability authoring contract.
- [`agents.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/agents.md) — upstream's equivalent guide.
