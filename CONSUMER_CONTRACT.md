# Consumer contract

Authoritative recipe for any tool — `agent-scaffold`, a hand-rolled CLI, an AI assistant — that consumes [`catalog.yaml`](catalog.yaml) and turns one of this repo's recipes into a working local project. Read once; pin to `contract_version`; ship.

The catalog is the single source of truth. Every field this document references lives in `catalog.yaml`; the markdown bodies are human-readable companions. A conforming consumer never reaches into this repo's `docs/**/*.md` directly except to load files declared in a recipe's `load_list[]` (which may include blueprint doc URLs the consumer resolves against its own agent-blueprints checkout).

> **Pin and check.** Read `catalog.contract_version` first. If it exceeds the maximum your consumer was tested against, refuse to proceed with a clear error. Older catalogs are forward-compatible (Pydantic `extra: ignore` style); newer catalogs are not.

---

## Step 1 — Fetch `catalog.yaml`

**Reads:** the catalog as a whole.
**Why:** every subsequent step resolves against this single artifact.

```python
import urllib.request, yaml
URL = "https://raw.githubusercontent.com/jagguvarma15/agent-deployments/main/catalog.yaml"
catalog = yaml.safe_load(urllib.request.urlopen(URL).read())
assert catalog["contract_version"] <= CONSUMER_MAX_CONTRACT_VERSION, (
    f"catalog.contract_version={catalog['contract_version']} exceeds "
    f"consumer max {CONSUMER_MAX_CONTRACT_VERSION}; upgrade consumer first"
)
```

**Failure mode if skipped:** consumer hand-walks the repo and re-implements the resolver; first upstream rename silently breaks it.

---

## Step 2 — Pick a recipe

**Reads:** `catalog.recipes[].slug` and `catalog.recipes[].title`.

```python
slug = "research-assistant"
recipe = next(r for r in catalog["recipes"] if r["slug"] == slug)
```

`recipe.title` is the H1 the user will see; `recipe.path` is the on-disk markdown if you need to fetch it for the load_list step.

**Failure mode if skipped:** consumer hardcodes file paths and breaks on the next recipe rename.

---

## Step 3 — Pick a runtime mode and apply swaps

**Reads:** `recipe.runtime_modes[<mode>]` and `recipe.capabilities[]`.

Every recipe ships a `default` mode plus optional modes like `local_only` and `hybrid_kafka`. Each mode declares `swaps:` — a map of capability ids (or `stack/<id>` references) that get substituted into the recipe's `capabilities[]` list when the consumer picks that mode.

```python
mode = recipe["runtime_modes"]["default"]
swaps = mode.get("swaps") or {}
effective_caps = [swaps.get(c, c) for c in recipe.get("capabilities", [])]
```

The mode may also declare `context_budget: {input_max, output_max}` — pass these into your prompt builder's token-budget enforcement instead of falling back to your global defaults.

**Failure mode if skipped:** consumer ignores mode swaps; `local_only` recipes still try to call Anthropic.

---

## Step 4 — Plan the prompt assembly within the 4-breakpoint budget

**Reads:** `recipe.load_list[]` (every entry carries a `cache_tier` value of `hot`, `warm`, or `dynamic`).

Anthropic's `cache_control` allows **at most 4 breakpoints per request**. Lay the load_list out as three tiers with a breakpoint at each boundary, then reserve the 4th slot for the most recent assistant turn in conversational recipes.

| Tier | Anthropic TTL | Contents |
|---|---|---|
| `hot` | 1h (`cache_control: {type: ephemeral, ttl: "1h"}`) | Pattern overview + framework guide + project-layout + `stack/llm-claude.md`. Stable across many requests; the 2.0× write cost amortizes inside the first hour. |
| `warm` | 5m (`cache_control: {type: ephemeral, ttl: "5m"}`) | Capability docs (lazy — only when the LLM asks for one), the recipe body itself. Churn possible inside a session. |
| `dynamic` | no `cache_control` | User input, tool results, anything that changes per request. |

```python
def assemble(load_list, recipe_body, user_input):
    blocks = []
    for entry in load_list:
        if not entry.get("required", True): continue
        if entry["cache_tier"] == "hot":
            blocks.append({"type": "text", "text": fetch(entry["path"])})
    blocks.append({"type": "text", "text": "<<HOT TIER END>>",
                   "cache_control": {"type": "ephemeral", "ttl": "1h"}})
    for entry in load_list:
        if entry["cache_tier"] == "warm":
            blocks.append({"type": "text", "text": fetch(entry["path"])})
    blocks.append({"type": "text", "text": recipe_body,
                   "cache_control": {"type": "ephemeral", "ttl": "5m"}})
    blocks.append({"type": "text", "text": user_input})  # dynamic
    return blocks
```

**4-breakpoint cap:** if the load_list implies more, collapse adjacent same-tier entries.
**Failure mode if skipped:** consumer pays full input rate on every request; cost shoots up 5–10× vs the same recipe with caching configured correctly.

---

## Step 5 — Render `.env.example`

**Reads:** `recipe.env_contract[]` and `recipe.env_overrides`.

`env_contract` is the generator-derived list of every env var the selected capabilities declare, with `source_capability` annotations and any defaults pulled from `env_overrides`. `env_overrides` is the recipe author's per-app defaults (`APP_PORT: 8000`, `MAX_STEPS: 5`).

```python
with open(".env.example", "w") as f:
    for var in recipe["env_contract"]:
        default = var.get("default", "")
        f.write(f"# from {var['source_capability']}\n")
        f.write(f"{var['name']}={default}\n")
```

**Failure mode if skipped:** generated project boots into a missing-env crash on first run.

---

## Step 6 — Sequence bootstrap by layer

**Reads:** `catalog.LAYER_ORDER` and each capability's `layer` + `bootstrap_step` + `bootstrap_inputs`.

`LAYER_ORDER` is the canonical sequence: `infrastructure → schema → data → identity → observability → eval → agent → frontend`. For each layer in order, bring up every selected capability whose `layer` matches, then run each capability's `bootstrap_step` against the recipe's `bootstrap_config`.

```python
caps_by_id = {c["id"]: c for c in catalog["capabilities"]}
for layer in catalog["LAYER_ORDER"]:
    layer_caps = [caps_by_id[cid] for cid in effective_caps
                  if caps_by_id[cid].get("layer") == layer["id"]]
    docker_services = [c["docker_service"] for c in layer_caps if c.get("docker_service")]
    run(f"docker compose up -d {' '.join(docker_services)}")
    for cap in layer_caps:
        if step := cap.get("bootstrap_step"):
            run_bootstrap_step(step, recipe.get("bootstrap_config", {}))
```

**Failure mode if skipped:** capabilities boot in undefined order; Langfuse tries to connect to Postgres before Postgres has a Langfuse database.

---

## Step 7 — Run the `smoke_test`

**Reads:** `recipe.smoke_test.{ready, exercise, assert_jq}`.

Three shell strings, run in order. `ready` blocks until the app's HTTP surface comes up (a `curl -sf` typically). `exercise` submits one representative request and writes the response to stdout. `assert_jq` is a jq expression evaluated against `exercise`'s stdout; it must be truthy (`true`, non-empty string, non-zero number) for the smoke pass to succeed.

```python
sh(recipe["smoke_test"]["ready"], timeout=300)            # block until ready
stdout = sh(recipe["smoke_test"]["exercise"], capture=True)
assert sh(f"echo '{stdout}' | jq -e '{recipe['smoke_test']['assert_jq']}'")
```

**Failure mode if skipped:** consumer declares "project generated" without ever proving the project starts and responds.

---

## Step 8 — Validate against `acceptance_contracts`

**Reads:** `recipe.acceptance_contracts.{http_endpoints, required_env, required_compose_services, smoke_assertions}`.

This block exists so the consumer can answer "does the generated project actually conform to the recipe" without re-reading the markdown. Every sub-block is optional but the generator validates structure when present.

```python
ac = recipe.get("acceptance_contracts") or {}
# http_endpoints
for ep in ac.get("http_endpoints", []):
    assert sh(f"curl -sf -X {ep.get('method', 'GET')} http://localhost:8000{ep['path']}"), ep
# required_env
for ev in ac.get("required_env", []):
    assert os.environ.get(ev["name"]), f"missing env {ev['name']} ({ev['source']})"
# required_compose_services
ps = sh("docker compose ps --services --filter status=running", capture=True).splitlines()
for svc in ac.get("required_compose_services", []):
    assert svc in ps, f"compose service {svc} not running"
# smoke_assertions
for sa in ac.get("smoke_assertions", []):
    assert sh(f"echo '{stdout}' | jq -e '{sa['jq']}'"), sa
```

**Failure mode if skipped:** consumer reports success on a project that's missing required env vars or unreachable endpoints; the user finds out at runtime.

---

## Step 9 — Monitor cache hit rate

**Reads:** each request's `cache_read_input_tokens` (Anthropic API response field).

Caches can silently regress. The March 2026 incident where 1h `cache_control` TTLs reverted to 5m (Anthropic `claude-code` issue #46829) only surfaced for consumers that monitored hit rate; everyone else discovered it on their next bill.

```python
for resp in response_stream:
    usage = resp.usage
    total_input = usage.input_tokens + usage.cache_read_input_tokens + usage.cache_creation_input_tokens
    hit_rate = usage.cache_read_input_tokens / total_input if total_input else 0
    emit_metric("anthropic.cache_hit_rate", hit_rate, tags={"recipe": slug, "mode": mode_name})
```

A sustained hit-rate drop on a recipe with a stable `load_list` is the leading indicator of a TTL regression upstream. Page on it.

**Failure mode if skipped:** consumer's per-request cost silently doubles when an upstream cache regression lands; the bill is the first signal.

---

## What changes between contract versions

`contract_version: 1` (this version) guarantees:

- Every `recipes[].load_list[]` entry carries a `cache_tier` (path-defaulted if not authored).
- `acceptance_contracts.*` validation rules listed above are enforced by the generator.
- The catalog top-level keys (`schema_version`, `generator_version`, `contract_version`, `blueprints`, `LAYER_ORDER`, `patterns`, `workflows`, `primitives`, `modifiers`, `compositions`, `recipes`, `capabilities`, `ports`, `compatibility`, `frameworks`, `stack`, `cross_cutting_docs`, `pattern_docs`, `primitive_docs`, `modifier_docs`, `suggestions`, `aliases`, `cross_cutting`, `non_recipe_stems`, `min_alias_length`) are stable.
- `ports[]` and `compatibility[]` are the **port-typed registry** layer (the abstract port contracts + the derived feature-model edges). They are additive — a `contract_version: 1` consumer that doesn't yet resolve them simply ignores them; the forthcoming scaffold resolver consumes them to choose a verified configuration. See [`MANIFEST_SCHEMA.md`](MANIFEST_SCHEMA.md) `### ports[]` / `### compatibility[]`.

A future `contract_version: 2` would (for example) make `cache_tier` mandatory rather than path-defaulted, or graduate `acceptance_contracts` from optional to required. Consumers pinned to `CONSUMER_MAX_CONTRACT_VERSION = 1` will halt cleanly when they fetch a `contract_version: 2` catalog — read the changelog, update the consumer, raise the pin.

`schema_version: 1` is a separate axis: it bumps when the YAML shape itself changes (a top-level key renamed, an entry type widened from string to mapping). See [`MANIFEST_SCHEMA.md`](MANIFEST_SCHEMA.md#schema_version-and-contract_version-the-split-version-model) for the full split-version model.

---

## See also

- [`MANIFEST_SCHEMA.md`](MANIFEST_SCHEMA.md) — the catalog's field-level schema.
- [`docs/recipes/SCHEMA.md`](docs/recipes/SCHEMA.md) — recipe frontmatter contract authors write against.
- [`docs/capabilities/README.md`](docs/capabilities/README.md) — capability frontmatter contract.
- [`docs/frameworks/SCHEMA.md`](docs/frameworks/SCHEMA.md) — framework frontmatter contract.
- [Anthropic prompt caching docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) — TTL options, pricing, the 4-breakpoint cap that Step 4 builds against.
