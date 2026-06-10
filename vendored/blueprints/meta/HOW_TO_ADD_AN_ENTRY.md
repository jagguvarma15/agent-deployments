# How to add an entry

The recommended landing page for anyone (first-time contributor, regular maintainer, Claude Code, Cursor, or another AI tool) adding a new pattern, primitive, or modifier — or proposing a brand-new cohort.

The repo is structured so that adding a new cognitive unit is **three steps**:

1. **Pick a cohort** (or [add a new one](#adding-a-brand-new-cohort)).
2. **Create the entry directory** with `metadata.json` + the tier markdown files declared in `tiers`.
3. **Run the generators**:
   ```bash
   node meta/validate-metadata.js --emit patterns-catalog.yaml
   node meta/generate-docs.js
   node meta/generate-website-data.js
   ```

Then commit everything (metadata + new directory + regenerated `patterns-catalog.yaml`, `website/src/data/patterns.ts`, and any docs the generators updated).

That's the whole flow. The rest of this doc is per-cohort recipes, the worked example, conventions, AI-tool prompts, and pitfalls.

---

## Quick start (copy-pasteable)

Below: adding a fictional new modifier called `audit_logging`.

```bash
# 1. Pick the cohort. Modifiers live at modifiers/.
mkdir -p modifiers/audit_logging/{prompts,schemas}

# 2a. Author metadata.json.
cat > modifiers/audit_logging/metadata.json <<'EOF'
{
  "id": "audit_logging",
  "name": "Audit Logging",
  "category": "modifier",
  "complexity": "Intermediate",
  "description": "Records every tool call + agent decision to an append-only audit log for compliance + replay.",
  "tiers": [
    "overview",
    "design",
    "implementation",
    "evolution",
    "observability",
    "cost-and-latency"
  ],
  "evolvesFrom": ["tool_use"],
  "composableWith": ["react", "plan_and_execute", "multi_agent"],
  "requires": ["append-only-log"],
  "appliesTo": ["any"],
  "tags": ["compliance", "audit", "replay"],
  "costTier": "low",
  "latencyTier": "low"
}
EOF

# 2b. Author each tier file. Templates exist for shape; copy from a sibling.
# See "Tier file conventions" below for what goes in each.
touch modifiers/audit_logging/{overview,design,implementation,evolution,observability,cost-and-latency}.md

# 2c. If category requires a state schema (per taxonomy.yaml), add it:
touch modifiers/audit_logging/schemas/__init__.py
cat > modifiers/audit_logging/schemas/state.py <<'EOF'
"""Canonical Pydantic v2 state schema for the Audit Logging modifier."""
from __future__ import annotations
from pydantic import BaseModel, Field

class AuditEntry(BaseModel):
    timestamp: str
    actor: str
    action: str
    payload: dict[str, object] = Field(default_factory=dict)

class AuditLoggingState(BaseModel):
    entries: list[AuditEntry] = Field(default_factory=list)
EOF

# 3. Run the generators.
node meta/validate-metadata.js --emit patterns-catalog.yaml
node meta/generate-docs.js
node meta/generate-website-data.js

# 4. Run the tests.
uv run --with 'pydantic>=2,PyYAML' pytest tests/

# 5. Commit + push as usual.
git add modifiers/audit_logging patterns-catalog.yaml website/src/data/patterns.ts \
        README.md modifiers/README.md foundations/choosing-a-pattern.md
git commit -m "Add audit_logging modifier"
```

## What the generators do for you

You authored one directory + one JSON file + one Python schema file. The generators then:

- **`validate-metadata.js`** — checks metadata.json against the taxonomy contract (required fields, category matches cohort, no broken cross-references). Emits an updated `patterns-catalog.yaml` containing your new entry.
- **`generate-docs.js`** — replaces `<!-- AUTO:... -->` blocks in every markdown file with regenerated content. Your new entry shows up in:
  - `README.md` workflow / agent / primitive / modifier tables
  - `patterns/README.md` (or `primitives/README.md` / `modifiers/README.md`) entry table
  - `foundations/choosing-a-pattern.md` Step 2 / Step 3 picker tables
- **`generate-website-data.js`** — regenerates `website/src/data/patterns.ts` from `patterns-catalog.yaml`. Your entry appears in the appropriate cohort array and in `PATTERN_COMPARISONS`.

You don't have to touch any of those generated files by hand — drift CI catches a forgotten regen.

---

## Per-cohort recipes

### Adding a pattern

```bash
mkdir -p patterns/<id>/{prompts,schemas,code/python}
# metadata.json must have category: 'agent' or 'workflow'
# tier files: at minimum overview.md, design.md, implementation.md
# Most patterns also ship evolution.md, observability.md, cost-and-latency.md
```

Agent patterns (`category: agent`) declare `evolvesFrom: [<workflow-id>]` so the website's evolution-edges renderer picks them up. Workflow patterns (`category: workflow`) declare `evolvesInto: [<agent-id>, ...]`.

If your pattern has a Pydantic state shape, author `schemas/state.py` per the convention in [`patterns/react/schemas/state.py`](../patterns/react/schemas/state.py).

### Adding a primitive

```bash
mkdir -p primitives/<id>/{prompts,schemas,code/python}
# metadata.json must have category: 'primitive'
# Tier file set is the same as patterns.
# evolvesFrom typically references the workflow that gave rise to the primitive
# (e.g. tool_use evolvesFrom prompt-chaining).
```

Primitives are orthogonal to patterns — they describe what the agent *has access to*, not what flow shape it follows.

### Adding a modifier

```bash
mkdir -p modifiers/<id>/{prompts,schemas,code/python}
# metadata.json must have category: 'modifier'
# Plus: appliesTo: list of pattern ids this modifier can wrap, or ['any']
```

Modifiers wrap a pattern with a transformation (a HITL approval gate, an audit overlay, …). They don't change the pattern's reasoning shape — they overlay a concern.

### Adding a brand-new cohort

You think a fourth category is needed (e.g. `guardrails/`, `evaluators/`, `memory_providers/`). Two-step:

1. **Append a cohort entry to `taxonomy.yaml`**:
   ```yaml
   - id: guardrails
     dir: guardrails
     label: Guardrail
     label_plural: Guardrails
     description: Policy enforcement layers (input filters, output validators, abuse detectors).
     category_values: [guardrail]
     catalog_key: guardrails
     requires_state_schema:
       when: "true"
     extra_fields: []
   ```
2. **`mkdir guardrails`** and add entries in the same shape as any existing cohort.

The validator, catalog emitter, schemas test, docs generator, and website data generator all read `taxonomy.yaml` — no other code change is required.

If your new cohort entries need to opt out of the state-schema requirement, set the predicate (e.g. `"category != 'lite'"`); see the existing `patterns:` cohort which exempts workflows.

---

## Tier file conventions

| Tier | What it covers |
|---|---|
| `overview.md` | 1-2 pages. Architecture diagram, when to use, headline tradeoffs. The picker hint that says *"here's what this entry is"*. |
| `design.md` | 3-5 pages. Component breakdown, data flow, failure modes, scaling. |
| `implementation.md` | 5-10 pages. Pseudocode, interfaces, testing strategy, pitfalls. |
| `evolution.md` | How this entry grew out of simpler entries. Cross-link to the parent. |
| `observability.md` | What to trace, what to log, key metrics, alarms. |
| `cost-and-latency.md` | Token math, p50/p95 expectations, budget envelope. |

Optional companion files:

- `prompts/` — example prompt templates the design doc references.
- `schemas/state.py` + `schemas/__init__.py` — Pydantic state model. **Required** unless your cohort's taxonomy.yaml entry sets `requires_state_schema.when` to `false` or a predicate that excludes your entry.
- `schemas/<other>.schema.json` — JSON Schemas for typed inputs/outputs your tier files reference.
- `code/python/` (and `code/typescript/`) — runnable framework-agnostic + per-framework implementations.

See [`meta/style-guide.md`](./style-guide.md) for the detailed style conventions per tier.

---

## Working with AI tools

The taxonomy + generators are designed to be easy to drive from an LLM / coding assistant. The instructions below show suggested prompts and the verification checklist to run after the AI hands you a diff.

### Claude Code (or any tool that can run shell commands)

Suggested prompt for adding a new modifier:

> "I want to add a new modifier to `agent-blueprints` called `audit_logging`. Use [`modifiers/human_in_the_loop/`](../modifiers/human_in_the_loop/) as the structural reference. The modifier should: (describe what it does in 2 sentences). Follow [`meta/HOW_TO_ADD_AN_ENTRY.md`](./HOW_TO_ADD_AN_ENTRY.md). Author all six tier files plus metadata.json + schemas/state.py + a sensible appliesTo list. Then run the three generators (validate-metadata --emit, generate-docs, generate-website-data) and the test suite, and report what changed."

Suggested prompt for adding a new pattern:

> "Add a new agent pattern called `<name>` to `agent-blueprints/patterns/`. Use [`patterns/react/`](../patterns/react/) as the structural reference. The pattern should: (describe the cognitive shape). Follow [`meta/HOW_TO_ADD_AN_ENTRY.md`](./HOW_TO_ADD_AN_ENTRY.md). It evolves from `<workflow_id>` and composes with `<list>`. Author all six tier files plus metadata.json + schemas/state.py. Run the generators and tests; show me the diff."

### Cursor / GitHub Copilot / handwritten

The same checklist applies. Drive the changes yourself with the same flow:

1. Read [`meta/HOW_TO_ADD_AN_ENTRY.md`](./HOW_TO_ADD_AN_ENTRY.md).
2. Pick a sibling entry as a structural reference.
3. Author the directory + metadata.json + tier files + state.py.
4. Run the generators (see [Quick start](#quick-start-copy-pasteable)).
5. Run the tests.
6. Review the auto-generated diffs in `README.md`, the per-cohort READMEs, `foundations/choosing-a-pattern.md`, `website/src/data/patterns.ts`, and `patterns-catalog.yaml` — they should reflect your new entry.

### Verification checklist (post-AI / pre-commit)

Whichever path you take, before committing:

- [ ] `node meta/validate-metadata.js` passes with no errors and the count line includes your new entry.
- [ ] `node meta/validate-metadata.js --emit patterns-catalog.yaml` produces no surprise diff beyond your new entry's row.
- [ ] `node meta/generate-docs.js` reports only the doc files that should have changed (the per-cohort README and any picker tables that include your cohort).
- [ ] `node meta/generate-website-data.js` updates `website/src/data/patterns.ts` to include your entry.
- [ ] `uv run --with 'pydantic>=2,PyYAML' pytest tests/` passes (all schemas import, sibling-code imports stay canonical).
- [ ] If you added a Pydantic state model, also add a `_CASES` entry in [`tests/test_schemas_importable.py`](../tests/test_schemas_importable.py) with the minimal valid kwargs.
- [ ] No broken markdown links. `grep -rn '\\.\\./<old-path>/' .` should not find references to your entry under the wrong cohort path.

---

## Common pitfalls

- **Category mismatch.** An entry under `primitives/` whose metadata says `category: agent` fails the validator. The expected category set per cohort lives in `taxonomy.yaml` (`cohorts[].category_values`).
- **Missing tier file.** If `metadata.json` lists `"tiers": ["overview", "design", "implementation"]` but `implementation.md` is missing, validation fails. Either author the file or remove it from `tiers`.
- **Broken cross-reference.** `evolvesFrom: ["typo_id"]` fails the cross-ref check. Cross-cohort refs are fine — but the referenced id must exist somewhere in the catalog.
- **Forgot to regenerate.** CI's drift gate catches this — `patterns-catalog.yaml`, the AUTO blocks, and `website/src/data/patterns.ts` must all be in sync with the source. Run the three generators in sequence and commit the result.
- **Skill triggers / pattern names colliding.** New entries should have unique `id` and `name`. The validator dedupes via the id-mismatch and registry checks; collisions surface as errors.

---

## Recommended GitHub Topics

For repo discoverability, the GitHub Topics on the repository's settings page should include (at minimum):

```
ai-agents
agent-patterns
llm-patterns
cognitive-patterns
claude
anthropic
mcp
workflows
agent-blueprints
```

Topics are set on the repo's web settings page (not via a file in the repo). Maintainers: keep this list in sync there when adding a new significant capability (e.g. if a future cohort like `guardrails/` lands, add `guardrails` here and on the settings page).

---

## See also

- [`../taxonomy.yaml`](../taxonomy.yaml) — the cohort declaration that drives every generator.
- [`./taxonomy.schema.json`](./taxonomy.schema.json) — JSON Schema for `taxonomy.yaml`.
- [`./validate-metadata.js`](./validate-metadata.js) — entry validation + catalog emit.
- [`./generate-docs.js`](./generate-docs.js) — AUTO marker replacement loop.
- [`./generate-website-data.js`](./generate-website-data.js) — website TS data regen.
- [`./contributing.md`](./contributing.md) — the broader pattern-author contract.
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — repo-level contributor guide.
- [`../PATTERNS_CATALOG_SCHEMA.md`](../PATTERNS_CATALOG_SCHEMA.md) — what the catalog itself looks like.
