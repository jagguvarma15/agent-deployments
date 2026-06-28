# Contributing to agent-deployments

Thank you for your interest in contributing! This guide covers how to contribute a new blueprint, improve existing docs, or submit a stack swap.

## Getting started

1. Fork and clone the repo
2. Read a few existing blueprints in `docs/recipes/` to understand the format
3. Check `docs/reference/` for project scaffolding templates

## Types of contributions

### Improvements to existing blueprints

1. Open an issue describing the improvement
2. Fork, branch (`improve/<short-description>`), and make changes
3. Ensure all internal markdown links still resolve
4. If you edited any recipe / capability / framework frontmatter, regenerate the catalog (`uv run scripts/generate_catalog.py`) and commit the resulting `catalog.yaml`
5. Submit a PR referencing the issue

### Stack swaps

Want to document how to swap a default pick (e.g., Qdrant to Pinecone)?

1. Use the `stack-swap` issue template
2. Add documentation to the relevant stack doc in `docs/stack/`
3. If the swap affects blueprint specs, update those too

### New blueprints

New blueprints must:

1. Use the `new-blueprint` issue template for discussion first
2. Declare the **three orthogonal picks** in frontmatter:
   - `agent_pattern:` — required, one id from `catalog.patterns[]` (see [`patterns/`](https://github.com/jagguvarma15/agent-blueprints/tree/main/patterns) for available ids)
   - `primitives:` — optional list, ids from `catalog.primitives[]` (memory, tool_use, skills, sub_agents)
   - `modifiers:` — optional list, ids from `catalog.modifiers[]` (guardrails, human_in_the_loop)
   The generator validates every id at build time and refuses to emit a catalog with an unresolved reference. See [`docs/recipes/SCHEMA.md`](docs/recipes/SCHEMA.md).
3. Include specifications for **both** Python and TypeScript tracks
4. Follow the 13-section blueprint template (see any existing recipe for reference)
5. Regenerate the catalog — after editing the new recipe's frontmatter (or any capability / framework / cross-cutting doc), run `uv run scripts/generate_catalog.py` and commit the resulting `catalog.yaml`. The drift CI gate enforces this.

### Blueprint template sections

Every blueprint should include:

- [ ] What it does
- [ ] Architecture (ASCII diagram)
- [ ] Data Models (Pydantic + Zod schemas)
- [ ] API Contract (endpoints with request/response JSON)
- [ ] Tool Specifications (if applicable)
- [ ] Prompt Specifications (actual prompts with design rationale)
- [ ] Key files (Python + TypeScript tracks)
- [ ] Implementation Roadmap (ordered build steps)
- [ ] Environment & Deployment (env vars table)
- [ ] Test Strategy (example tests per tier)
- [ ] Eval Dataset (inline golden examples)
- [ ] Design Decisions (trade-offs and rationale)

## Code style

- **Markdown**: clean formatting, consistent heading levels
- **Code blocks**: include language identifiers (```python, ```typescript)
- **Links**: use relative paths within docs/

## Commit messages

Use concise, descriptive commit messages:
- `add: memory-assistant blueprint`
- `fix: incorrect schema in docs-rag-qa data models`
- `docs: update stack rationale for Qdrant version bump`

## PR checklist

- [ ] I have read the contributing guide
- [ ] Both language tracks are specified (for new blueprints)
- [ ] All internal markdown links resolve
- [ ] If I edited any recipe / capability / framework frontmatter: I regenerated `catalog.yaml` (`uv run scripts/generate_catalog.py`) and committed the result
- [ ] I have not committed secrets or API keys

## Questions?

Open a discussion or issue. We're happy to help scope contributions before you invest time building.
