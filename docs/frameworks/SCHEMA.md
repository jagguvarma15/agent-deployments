# Framework doc schema

Canonical specification for the YAML frontmatter and body shape every doc under `docs/frameworks/` must follow. Two consumers depend on it:

- `comparison.md` cells link into each framework doc by H2 anchor slug. Adding or renaming an H2 in a way that breaks a cell anchor is a contract violation; cell links and the canonical H2 set move together.
- `agent-scaffold` reads the frontmatter (`id`, `language`, `package`, `versions`) to surface a pin in the wizard and resolve framework-specific docs at generation time. Frontmatter shape changes are observable in scaffold behavior.

> Authoritative since: introduction of this file.
> Worked reference: [`langchain.md`](langchain.md) — frontmatter + body conform to the schema below and can be copied verbatim as a starting point for a new framework doc.

## Why this exists

Until this document landed, the framework doc body shape lived in two parallel skeletons. The five legacy docs (`langgraph.md`, `pydantic-ai.md`, `crewai.md`, `mastra.md`, `vercel-ai-sdk.md`) shared a `Core abstractions / Patterns it supports well / Patterns where it's awkward / Idiomatic minimal example / Strengths / Trade-offs / Used in this repo / Reference implementations` skeleton. The newer docs (`langchain.md`, `claude-agent-sdk.md`) used a capability-oriented skeleton (`When to choose / Minimal agent / Tools / Structured output / Memory / Observability / Streaming / Retrieval / Testing / Anti-patterns / Composition matrix`). `comparison.md` papered over the drift cell-by-cell — every matrix entry resolved against whichever skeleton's anchor was tightest, with no contract preventing the next framework doc from inventing a third.

This document pins the canonical body H2 set and makes the cell-anchor contract explicit. Adding a new framework doc is now a copy-and-fill operation, not a structural decision.

## Frontmatter contract

Every framework doc opens with a YAML frontmatter block. Fields:

### Required

- **`id`** *(string)* — the framework slug the scaffold REPL accepts. snake_case for multi-word: `langgraph`, `pydantic_ai`, `vercel_ai_sdk`. Must match the `id:` literal that `agent-scaffold`'s framework picker recognizes; renaming here is an observable behavior change.
- **`language`** *(string)* — `python` or `typescript`. Drives which language-track recipes resolve this framework as a candidate.
- **`package`** *(string)* — PyPI or npm distribution name (`langgraph`, `pydantic-ai`, `@vercel/ai`). The recipes and language-hints loaders use this to pin dependencies in generated projects.
- **`versions.minimum`** *(string)* — current canonical floor with operator (e.g. `">=0.1.0"`, `"^4.0.0"`, or exact `"0.3.21"`). The `**Version pinned:**` line in the body mirrors this for human readers.
- **`versions.last_known_good`** *(string)* — the highest version in the `Recommended` row of the body's `## Version notes` table. Lets the scaffold gate generated `pyproject.toml` / `package.json` pins on a tested ceiling without re-parsing the table.
- **`versions.notes`** *(string)* — the one-line summary sentence opening the body's `## Version notes` section. Verbatim copy. Surfaces in the scaffold's wizard preview so users see why the floor / known-good shape they're about to ship is shaped the way it is.

### Optional

- **`extra_packages`** *(list of `{name, minimum}` objects)* — companion deps the framework requires beyond the baseline language environment. Each entry is a mapping with `name` (PyPI / npm slug) and `minimum` (version constraint string). Example: LangGraph hierarchical recipes need `langgraph-supervisor`; it lives in `extra_packages`, not the recipe's `recipe_dependencies`, because the dependency is framework-owned.

### Example frontmatter

```yaml
---
id: langchain
language: python
package: langchain
versions:
  minimum: ">=0.3.0"
  last_known_good: "0.3.27"
  notes: "0.3.x is the stable agent surface; `create_tool_calling_agent` + `AgentExecutor` are the post-0.2 successor to `initialize_agent`."
extra_packages:
  - {name: langchain-anthropic, minimum: ">=0.2.0"}
  - {name: langchain-core, minimum: ">=0.3.0"}
---
```

## Body shape: canonical H2 set

Every framework doc body contains these H2 sections in this order. Slug anchors (GitHub-derived) are the interface `comparison.md` cells link against; renaming an H2 silently breaks every matrix cell that points at it.

| H2 heading | Anchor slug | Required? | Purpose |
|---|---|---|---|
| `## When to choose <Framework>` | `when-to-choose-<framework>` | Required | Intro paragraph + a short bullet list of the framework's core abstractions and the situations it's the best fit for. Replaces the legacy `Core abstractions` + `Strengths` sections. |
| `## Minimal agent` | `minimal-agent` | Required | The shortest end-to-end example that exercises the framework's idiomatic surface. Replaces the legacy `Idiomatic minimal example`. |
| `## Tools` | `tools` | Required | How tool registration and dispatch work. One paragraph minimum; a snippet if there's a non-obvious registration shape. |
| `## Structured output` | `structured-output` | Required | The idiomatic way to bind a typed schema to the model's response. |
| `## Memory` | `memory` | Required | First-class conversation / state memory primitives, if any. **If absent, write one short paragraph explaining the absence and pointing at the framework-agnostic alternative** (e.g. `## Memory\n\nMastra ships no Memory primitive; use the conversation-buffer pattern at [memory](../patterns/memory.md).`). Empty headings break the matrix; a one-paragraph absence preserves the anchor. |
| `## Streaming` | `streaming` | Required | Token / event streaming surface. Same absence rule as Memory. |
| `## Observability` | `observability` | Required | Native tracing integration (LangSmith, OTel, framework-specific). Same absence rule. |
| `## Retrieval` | `retrieval` | Optional | Present only when the framework has a first-class retriever surface (e.g. LangChain's `Retriever` interface, Mastra's RAG primitives). Skip the heading entirely if the framework treats retrieval as a tool concern. |
| `## Testing` | `testing` | Optional | Present when the framework has a documented test seam (fake LLM, mock tool runner, replay harness). Skip if test seams are user-rolled. |
| `## Anti-patterns` | `anti-patterns` | Required | Cases where the framework is the wrong fit. Replaces the legacy `Patterns where it's awkward` + `Trade-offs`. |
| `## Composition matrix` | `composition-matrix` | Optional | Table mapping the framework against the repo's patterns (which are first-class, which are awkward, which are user-built). Recommended for frameworks where the matrix coverage is wide enough to warrant in-doc surfacing; otherwise rely on the cross-doc `comparison.md`. |
| `## Version notes` | `version-notes` | Required | Opens with the one-line summary sentence that mirrors `versions.notes` in frontmatter. Followed by a `| Version | Status | Notes |` table where the highest `Recommended` row's version equals `versions.last_known_good`. Optional `### Upgrade gotchas` and `### Why these bounds` subsections follow. |

### Tail subsections

After the canonical H2 set, frameworks may include one optional `## Used in this repo` H2 mapping recipes to the framework's role within them, plus a `## Reference implementations` bullet list cross-linking to those recipes. These are not part of the canonical anchor set — cells in `comparison.md` should never link here.

## Cell-link contract

`comparison.md` cells link into framework docs by H2 anchor slug. The contract:

- Every cell anchor must resolve to an H2 in the canonical set above (or an optional subsection that's documented in the table). Anchors targeting legacy section names (`#core-abstractions`, `#patterns-it-supports-well`, `#strengths`, `#trade-offs`, `#idiomatic-minimal-example`, `#patterns-where-its-awkward`) are schema violations.
- When a cell needs to point at framework-specific deep-dive content (e.g. LangGraph's event-driven graph composition), the deep dive lives as a `###` subsection under the closest canonical H2 (`### Event-driven state machine` under `## Composition matrix`, in that example). Cells link to the H2 slug, not the H3 — H3 slugs are not part of the contract.
- New cells against new anchors are a schema violation until the anchor is added here.

The verification script in the PR that landed this schema audits every `comparison.md` cell anchor against the per-doc canonical H2 set; CI for this is a follow-up (see `frameworks/README.md` for the punt note).

## Required vs. recommended summary

| Field | Required? | Consumer |
|---|---|---|
| `id` | Yes | scaffold REPL framework picker |
| `language` | Yes | recipe language gate |
| `package` | Yes | recipe `recipe_dependencies` defaults |
| `versions.minimum` | Yes | scaffold + recipe pinning |
| `versions.last_known_good` | Yes | wizard preview + scaffold-side ceiling gate |
| `versions.notes` | Yes | wizard preview prose |
| `extra_packages` | Optional | recipe `recipe_dependencies` augment |

## Conformance

A framework doc is schema-conformant when:

- Frontmatter carries every required field with allowed types and values.
- The body's first H1 names the framework (`# Framework: <Name>`).
- Every canonical H2 in the required column above is present in declared order. Absence paragraphs (Memory / Streaming / Observability) are acceptable; absent H2 headings are not.
- Every `comparison.md` cell linking to this doc resolves to a canonical anchor.

Spot-check:

```bash
# H2 set sanity — every required heading is present
for f in docs/frameworks/{langgraph,pydantic-ai,crewai,mastra,vercel-ai-sdk,langchain,claude-agent-sdk}.md; do
  grep -E '^## ' "$f" | head -20
done

# Cell anchors all resolve
uv run --with pyyaml python3 - <<'PY'
import pathlib, re
root = pathlib.Path("docs/frameworks")
cells = re.findall(
    r"\]\(([a-z-]+\.md)#([^)]+)\)",
    (root / "comparison.md").read_text(),
)
fail = 0
for f, anchor in set(cells):
    target = (root / f).read_text()
    slugs = {
        re.sub(r"[^a-z0-9-]", "", line.lower().lstrip("#").strip().replace(" ", "-"))
        for line in target.splitlines() if line.startswith("## ") or line.startswith("### ")
    }
    if anchor not in slugs:
        print(f"MISSING {f}#{anchor}")
        fail += 1
print("anchor audit:", "OK" if fail == 0 else f"{fail} missing")
PY
```

## See also

- [`README.md`](README.md) — framework catalog index and quick-pick decision tree.
- [`comparison.md`](comparison.md) — the capability matrix whose cells consume the canonical anchor set.
- [`../recipes/SCHEMA.md`](../recipes/SCHEMA.md) — companion contract for recipe frontmatter (the other half of the deployments-side surface).
