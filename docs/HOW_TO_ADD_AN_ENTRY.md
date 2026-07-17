# How to add a recipe, capability, framework, or topology

The contract is executable: **an entry is valid when the lint passes.** There is no
separate review checklist to remember — the producer-side validator in
`scripts/generate_catalog.py` encodes every rule, and the consumer mirror
(`agent-scaffold lint-content`) runs the same rules against any resolved
deployments source. When both are green, the entry is done.

```bash
# Producer (this repo): validate content + verify catalog.yaml is fresh.
python scripts/generate_catalog.py --check
python scripts/test_catalog_validation.py

# Consumer (agent-scaffold): same rules against this tree.
agent-scaffold lint-content --deployments-path .
```

If you changed any source frontmatter, regenerate and commit the catalog:

```bash
python scripts/generate_catalog.py   # rewrites catalog.yaml
```

## Add a capability — `docs/capabilities/<kind>/<name>.md`

1. `kind` must be one of the allowed kinds (see
   [`capabilities/README.md`](capabilities/README.md) → *Capability kinds*).
   The generator fails closed on an unknown kind.
2. `id` is dotted `<kind>.<name>` and must match the file path.
3. `card.name` and `card.description` are required and non-empty.
4. Pick a host port that does not collide with any service in a recipe that will
   resolve this capability. The canonical allocation is in
   [`cross-cutting/project-layout.md`](cross-cutting/project-layout.md) (app 8000,
   chroma 8002, zep 8003, frontends 3000/5173/8501, …). The lint rejects two
   services in a recipe's resolved stack binding the same host port.
5. Declare `layer`, `requires`, `cost_tier` per the v0.3 contract.
6. If the capability can run in more than one place (managed cloud vs the
   compose fragment), declare `hosting: [cloud, docker]` (or the applicable
   subset) so consumers can offer the choice. Optional — absent means
   consumers infer from `docker.service` presence.

## Add a recipe — `docs/recipes/<name>.md`

1. `topology` (when present) must be one of the canonical values
   ([`recipes/SCHEMA.md`](recipes/SCHEMA.md) → *topology*).
2. Every `capabilities[]` id must resolve to a capability file; every
   `agent_pattern` / `primitives[]` / `modifiers[]` must resolve to a blueprint
   cohort id.
3. `required_files` must name a recognized backend entry point
   (`main.py` / `app.py` / `server.py` / `index.ts` / …). Run discovers the
   entry point by basename, so a recipe that ships `app/` source but lists no
   entry point passes generation yet fails to launch.
4. Every `load_list[].path` must resolve to a file on disk (the producer fails
   closed; the consumer fails open with a warning).
5. Any provider you advertise in a `runtime_modes` description (openai, cohere,
   qdrant, zep, …) should be backed by a `capabilities[]` entry **and** a
   `recipe_dependencies` package. Unbacked advertisements are flagged as
   advisory warnings, not hard failures — but they mean the advertised stack
   can't actually run.

## Add a framework or topology

- **Framework** — drop `docs/frameworks/<id>.md`, then reference it from at least
  one recipe's `load_list` (typically gated `when: language == '…'`). A framework
  no recipe references is flagged as an advisory coverage gap.
- **Topology** — extend the canonical list in **three** places that a parity test
  ties together: `VALID_TOPOLOGIES` in `scripts/generate_catalog.py`, the
  *Allowed values* line in [`recipes/SCHEMA.md`](recipes/SCHEMA.md), and the
  `Topology` enum in agent-scaffold (`src/agent_scaffold/topology.py`). The same
  three-way tie applies to capability kinds (`VALID_CAPABILITY_KINDS`, the
  *Allowed kinds* line, and scaffold's `_KNOWN_KINDS`).

## Why the lint, not a checklist

The drift classes these rules catch (a recipe whose advertised stack, capability
ids, dependencies, and code disagree; a dead load-list link; two services on the
same host port; a kind typo) all pass a human eyeball and only surface when a
generated project fails `docker compose up`. The lint makes "conformant" a thing
a machine checks on every PR via `.github/workflows/catalog-drift.yml`.
