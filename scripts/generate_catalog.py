#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["PyYAML>=6.0"]
# ///
"""Generate catalog.yaml from this repo's frontmatter + agent-blueprints' catalog.

This script is the **single source of truth** for `catalog.yaml`. The file is
auto-generated, not hand-edited — the CI drift check in
`.github/workflows/catalog-drift.yml` fails any PR that commits a catalog
diverging from a fresh regen.

What it does (in order):

1. Walks ``docs/recipes/*.md``, ``docs/capabilities/**/*.md``,
   ``docs/frameworks/*.md``, ``docs/stack/*.md``, ``docs/cross-cutting/*.md``.
   Parses each file's YAML frontmatter via PyYAML.
2. Reads ``patterns-catalog.yaml`` from the committed, SHA-pinned reference
   copy of agent-blueprints at ``reference/blueprints/patterns-catalog.yaml``
   (refreshed on a blueprints release by ``sync-blueprints.yml``). Extracts
   its ``patterns[]``, ``workflows[]``, and ``compositions[]`` blocks and
   embeds them. Override the source via ``--blueprints-catalog-url`` for
   local iteration against an unmerged blueprints branch.
3. Enumerates ``pattern_docs[]`` as GitHub URLs derived from the reference
   catalog's cohort entries (``patterns``/``workflows``/``primitives``/
   ``modifiers``). The consumer (agent-scaffold) resolves these against its
   own directly-fetched blueprints checkout; no vendored tree is committed.
4. Reads ``scripts/_seed_aliases.yaml`` for the v1 alias / cross-cutting /
   non-recipe-stems / min-alias-length blocks. (v1.1 will move alias data
   into per-doc frontmatter.)
5. Emits ``catalog.yaml`` (or ``--out <path>``) via deterministic PyYAML dump
   (sort_keys=False, no flow style, no timestamps).

Determinism notes:

- The output is a pure function of input file content: no ``generated_at``,
  no commit SHAs, no environment-dependent fields, no record of which URL
  the blueprints catalog was fetched from. That's load-bearing for the
  drift CI — running the generator with ``--blueprints-catalog-url`` set
  to a local file or to the live URL must produce identical bytes given
  identical input content.
- Blueprints version tracking happens implicitly via the embedded
  ``patterns[]`` / ``workflows[]`` / ``compositions[]`` content. If
  blueprints changes, those blocks change, and the deployments catalog
  diffs. No separate ``upstream_sha`` field needed.
- All collections are sorted before emit: recipes / capabilities / frameworks
  / stack / cross-cutting / patterns by their natural primary key.
- Aliases and cross-cutting maps inherit the seed file's insertion order
  (which is the legacy ALIAS_TABLE order from scaffold).

Local development:

    # Default: read the committed reference/blueprints/patterns-catalog.yaml.
    python scripts/generate_catalog.py

    # Run against an unmerged blueprints branch URL:
    python scripts/generate_catalog.py \\
      --blueprints-catalog-url \\
      https://raw.githubusercontent.com/jagguvarma15/agent-blueprints/feat/patterns-catalog/patterns-catalog.yaml

    # Or against a local file:
    python scripts/generate_catalog.py \\
      --blueprints-catalog-url \\
      file:///Users/me/Desktop/agent-blueprints/patterns-catalog.yaml
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from collections import OrderedDict
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = 1
GENERATOR_VERSION = "1.4.0"

# Contract version: semantic guarantees consumers can pin against. Independent
# of schema_version (YAML shape). Bumped when stable-field semantics change or
# new fields graduate from optional to required. Additive optional fields keep
# this version stable. See MANIFEST_SCHEMA.md § contract_version.
CONTRACT_VERSION = 1

# Valid enum for recipes[].load_list[].cache_tier. Maps to Anthropic
# cache_control TTLs in the schema doc; the generator only enforces the enum.
VALID_CACHE_TIERS = frozenset(["hot", "warm", "dynamic"])

# Formal grammar for recipes[].load_list[].when predicates. These regexes
# mirror the consumer-side evaluator in agent-scaffold's
# context.evaluate_load_list_predicate EXACTLY — the consumer stays fail-open
# (an unparseable predicate loads the doc, with a warning) while this
# generator fails CLOSED so a malformed predicate never ships in the catalog.
# Grammar (see docs/recipes/SCHEMA.md § load_list[].when):
#   predicate := scalar_eq | contains
#   scalar_eq := ("language" | "framework" | "topology") "==" quoted_value
#   contains  := "capabilities" "contains" quoted_value
#   quoted_value := "'" <non-quote chars> "'" | '"' <non-quote chars> '"'
LOAD_LIST_PRED_EQ_RE = re.compile(
    r"^\s*(language|framework|topology)\s*==\s*['\"]([^'\"]+)['\"]\s*$"
)
LOAD_LIST_PRED_CONTAINS_RE = re.compile(
    r"^\s*capabilities\s+contains\s+['\"]([^'\"]+)['\"]\s*$"
)

# acceptance_contracts sub-blocks that every "Blueprint (validated)" recipe
# must explicitly declare (empty lists are allowed — the author consciously
# states "none" — but the key must be present).
ACCEPTANCE_CONTRACT_BLOCKS = (
    "http_endpoints",
    "required_env",
    "required_compose_services",
    "smoke_assertions",
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = REPO_ROOT / "docs"
SUGGESTIONS_ROOT = DOCS_ROOT / "suggestions"

# Blueprints is referenced directly (no vendir vendoring): the catalog is read
# from a committed, SHA-pinned reference copy (keeps the build offline +
# deterministic), and doc paths are emitted as GitHub URLs that the consumer
# (agent-scaffold) resolves against its own directly-fetched blueprints checkout.
REFERENCE_BLUEPRINTS_DIR = REPO_ROOT / "reference" / "blueprints"
BLUEPRINTS_DOC_URL_BASE = "https://github.com/jagguvarma15/agent-blueprints/blob/main/"
DEFAULT_BLUEPRINTS_CATALOG_URL = str(REFERENCE_BLUEPRINTS_DIR / "patterns-catalog.yaml")

# ---------------------------------------------------------------------------
# Bootstrap-sequencing contract. Every capability declares which layer it
# belongs to via `layer:` in its frontmatter; consumers run bootstrap steps
# layer-by-layer in this order. See MANIFEST_SCHEMA.md § "LAYER_ORDER" for
# the full semantics.
# ---------------------------------------------------------------------------

LAYER_ORDER: list[tuple[str, str]] = [
    (
        "infrastructure",
        "Stateful services with own healthchecks (Postgres, Redis, Kafka, vector DBs, Temporal).",
    ),
    (
        "schema",
        "Schema migrations + initial DDL on the infrastructure layer (alembic upgrade head, prisma migrate deploy).",
    ),
    (
        "data",
        "Data-shape provisioning (vector collections, kafka topics, redis streams). Reads bootstrap_inputs from upstream caps.",
    ),
    (
        "identity",
        "User / tenant / service-account provisioning. Empty in MVP recipes; reserved for auth provider bootstrap.",
    ),
    (
        "observability",
        "Tracing + log-aggregation backends (Langfuse, Langsmith, Grafana stack). Often `requires: [relational]`.",
    ),
    (
        "eval",
        "Eval harnesses (promptfoo, deepeval, ragas) — config + golden datasets prepped before the agent boots.",
    ),
    (
        "agent",
        "The agent process itself. Last to boot; first to be smoke-tested.",
    ),
    (
        "frontend",
        "User-facing UI / chat surface. Optional; only present when the recipe declares a frontend capability.",
    ),
]
LAYER_IDS = frozenset(layer_id for layer_id, _ in LAYER_ORDER)

VALID_COST_TIERS = frozenset(["free", "fixed-monthly", "per-call"])
VALID_RECIPE_COST_TIERS = frozenset(["free", "low", "medium", "high"])
# Canonical recipe `topology` values — the single source of truth documented in
# docs/recipes/SCHEMA.md (#### topology → Allowed values). The scaffold's
# Topology enum mirrors this list; its tests/test_topology.py fails on drift.
VALID_TOPOLOGIES = frozenset(
    [
        "single",
        "chain",
        "parallel",
        "event-driven",
        "multi-agent-flat",
        "multi-agent-hierarchical",
    ]
)
# Canonical capability `kind` values — the single source of truth documented in
# docs/capabilities/README.md (## Capability kinds) and docs/recipes/SCHEMA.md
# (Allowed kinds). The scaffold's capabilities._KNOWN_KINDS mirrors this list;
# its tests/test_content_lint.py fails on drift. Unlike the consumer (which
# carries an unknown kind as `unresolved`), the producer fails CLOSED so a
# typo'd kind never ships in the catalog.
VALID_CAPABILITY_KINDS = frozenset(
    [
        # v0.2 infrastructure cohort.
        "vector_db",
        "cache",
        "relational",
        "queue",
        "obs",
        "eval",
        "frontend",
        "host",
        # 2026-SOTA agent-native cohort.
        "mcp",
        "sandbox",
        "durable",
        "memory_store",
        "guardrail",
        "embedding",
        "live_data",
        "rerank",
        # Runtime key bootstrap (auth.key-bootstrap).
        "auth",
        # Core generation primitives — emitted project structure (spec / prompts
        # / io / tool registry / step-log / tracing), seeded by the scaffold's
        # tier presets. Not provisioned infra.
        "core",
    ]
)

# Recognized backend entry-point basenames. A recipe that ships application
# source must list one of these in `required_files`, or run (which discovers
# the entry point by basename) has nothing the generation contract guaranteed.
# The Python subset must stay a SUPERSET of agent-scaffold's
# steps/launch_backend.py `_ENTRY_CANDIDATES` (main/app/server/api/asgi.py) so
# anything run can launch is a valid declared entry point; the .ts/.js
# basenames cover the TypeScript track. Mirrored verbatim by agent-scaffold's
# content_lint.ENTRY_POINT_BASENAMES (pinned by a parity test in both repos).
ENTRY_POINT_BASENAMES = frozenset(
    [
        "main.py",
        "app.py",
        "server.py",
        "api.py",
        "asgi.py",
        "__main__.py",
        "index.ts",
        "index.js",
        "main.ts",
        "server.ts",
        "app.ts",
    ]
)

# Providers that, when named in a runtime_modes mode description, should be
# backed by a matching capability id (substring) OR a recipe dependency
# (substring) — the advisory check warns only when BOTH are absent. Keyed by the
# lowercase token to scan for. The base LLM (Anthropic/Claude) and local-swap
# runtimes (vLLM/Llama/SearXNG) are intentionally absent — they are stack/llm
# swaps, not capabilities. Mirrored verbatim by agent-scaffold's content_lint.py
# (pinned by a parity test in both repos). Advisory: never fails the build.
ADVERTISED_PROVIDERS: dict[str, tuple[str, str]] = {
    # token: (capability-id substring, dependency-name substring)
    "qdrant": ("qdrant", "qdrant"),
    "chroma": ("chroma", "chroma"),
    "pgvector": ("pgvector", "pgvector"),
    "openai": ("embedding.openai", "openai"),
    "cohere": ("rerank.cohere", "cohere"),
    "zep": ("memory_store.zep", "zep"),
}
"""Default source for the blueprints catalog. Reads the committed, SHA-pinned
reference copy at ``reference/blueprints/patterns-catalog.yaml`` (refreshed on
a blueprints release by ``sync-blueprints.yml``). Override via
``--blueprints-catalog-url`` to point at a URL or a different local path when
iterating against an unmerged upstream branch."""

DEFAULT_BLUEPRINTS_REPO = "jagguvarma15/agent-blueprints"
DEFAULT_BLUEPRINTS_BRANCH = "main"

NETWORK_TIMEOUT_SECONDS = 10.0

# Source files for each section. Globs are relative to DOCS_ROOT.
RECIPE_GLOB = ("recipes", "*.md")
CAPABILITY_GLOB = ("capabilities", "*", "*.md")
FRAMEWORK_GLOB = ("frameworks", "*.md")
STACK_GLOB = ("stack", "*.md")
CROSS_CUTTING_GLOB = ("cross-cutting", "*.md")
PORT_GLOB = ("ports", "*.md")

# Port protocol/concern vocabularies — mirror the blueprints kernel IR
# (core/spec/ir.schema.json $defs.port.protocol / $defs.cross_cutting.concern).
PORT_PROTOCOLS = frozenset({"model", "tools", "memory", "runtime", "agents"})
PORT_CONCERNS = frozenset({"observability", "guardrails", "budgets", "context_assembly", "eval"})

# Frontmatter regex matches identical to scaffold's discovery.py:_parse_frontmatter
# so the generator and the consumer agree on what counts as frontmatter.
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)

# Used for non-recipe filtering — populated from the seed file at runtime
# but defaults match scaffold's _NON_RECIPE_STEMS so dev-mode (skip seed)
# still does the right thing.
DEFAULT_NON_RECIPE_STEMS = frozenset(
    ["readme", "schema", "index", "changelog", "contributing", "license", "templates"]
)


# ---------------------------------------------------------------------------
# Frontmatter + H1 parsing
# ---------------------------------------------------------------------------


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return ``(frontmatter_dict, body)`` for a markdown file.

    Empty dict if no frontmatter or if YAML parsing fails — same fail-soft
    behavior the scaffold uses, so we never silently produce a catalog with
    a half-parsed entry.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        loaded = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}, text[match.end() :]
    if not isinstance(loaded, dict):
        return {}, text[match.end() :]
    return loaded, text[match.end() :]


def first_h1(text: str) -> str | None:
    match = _H1_RE.search(text)
    return match.group(1).strip() if match else None


def default_cache_tier(load_path: str) -> str:
    """Path-based default for ``recipes[].load_list[].cache_tier``.

    Load_list paths are recipe-relative (``../frameworks/...``,
    ``../stack/...``) or absolute GitHub URLs for blueprint docs. Strip
    leading ``./`` and ``../`` segments to a canonical form, then bucket by
    directory.

    Defaults:
      - blueprint doc URLs (``.../agent-blueprints/...``) → hot
      - ``frameworks/**``, ``stack/**``, ``cross-cutting/project-layout.md`` → hot
      - ``cross-cutting/**`` (other), ``capabilities/**`` → warm
      - ``recipes/**`` (recipe body) → warm
      - Anything not matched → dynamic
    """
    if "/agent-blueprints/" in load_path:
        return "hot"
    p = load_path
    while p.startswith("./"):
        p = p[2:]
    while p.startswith("../"):
        p = p[3:]
    if p.startswith("frameworks/") or p.startswith("stack/"):
        return "hot"
    if p == "cross-cutting/project-layout.md":
        return "hot"
    if p.startswith("cross-cutting/") or p.startswith("capabilities/"):
        return "warm"
    if p.startswith("recipes/"):
        return "warm"
    return "dynamic"


# ---------------------------------------------------------------------------
# Source walkers
# ---------------------------------------------------------------------------


def iter_files(glob_parts: tuple[str, ...], non_recipe_stems: frozenset[str]) -> list[Path]:
    """Walk DOCS_ROOT/<glob_parts> and yield .md files, skipping non-content stems."""
    pattern = "/".join(glob_parts)
    files = sorted(DOCS_ROOT.glob(pattern))
    return [
        p
        for p in files
        if p.is_file() and p.stem.lower() not in non_recipe_stems and not p.name.startswith(".")
    ]


def collect_recipes(non_recipe_stems: frozenset[str]) -> list[dict[str, Any]]:
    """Build the recipes[] block from docs/recipes/*.md frontmatter."""
    out: list[dict[str, Any]] = []
    for path in iter_files(RECIPE_GLOB, non_recipe_stems):
        text = path.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)
        if not fm:
            # A markdown file under docs/recipes/ with no frontmatter isn't a
            # recipe — skip silently. (e.g. docs/recipes/legacy/notes.md if any.)
            continue
        title = first_h1(body) or first_h1(text)
        if not title:
            print(f"warning: {path.relative_to(REPO_ROOT)}: no H1, skipping", file=sys.stderr)
            continue
        # Refuse hand-authored env_contract — it's auto-derived by build_catalog.
        if "env_contract" in fm:
            raise SystemExit(
                f"error: {path.relative_to(REPO_ROOT)}: env_contract is auto-derived; "
                "remove it from the recipe frontmatter."
            )
        entry: dict[str, Any] = OrderedDict()
        entry["slug"] = path.stem
        entry["path"] = str(path.relative_to(REPO_ROOT).as_posix())
        entry["title"] = title
        # Pass-through fields in the order the scaffold's Recipe model expects.
        # Includes the v0.3 local-bringup additions (runtime_modes, smoke_test,
        # cost_profile, model_recommendation, env_overrides, est_tokens, plus
        # the additive advanced fields).
        for key in (
            "status",
            "languages",
            "topology",
            "complexity",
            "agent_pattern",
            "agent_role",
            "primitives",
            "modifiers",
            "required_files",
            "recipe_dependencies",
            "external_services",
            "capabilities",
            "bootstrap_config",
            "roles",
            "load_list",
            "mcp_servers",
            "skills",
            "guardrails",
            "sandbox",
            "durable_workflow",
            "runtime_modes",
            "smoke_test",
            "cost_profile",
            "model_recommendation",
            "env_overrides",
            "est_tokens",
            "acceptance_contracts",
        ):
            if key in fm:
                entry[key] = fm[key]
        # Compute cache_tier defaults on every load_list entry. Authored values
        # win after enum validation; missing values get the path-based default.
        # Validation lives in validate_recipe_references; here we only fill in.
        load_list = entry.get("load_list") or []
        if isinstance(load_list, list):
            normalized: list[Any] = []
            for item in load_list:
                if not isinstance(item, dict):
                    normalized.append(item)
                    continue
                merged = OrderedDict(item)
                if "cache_tier" not in merged and isinstance(merged.get("path"), str):
                    merged["cache_tier"] = default_cache_tier(merged["path"])
                normalized.append(merged)
            entry["load_list"] = normalized
        out.append(entry)
    out.sort(key=lambda e: e["slug"])
    return out


def collect_capabilities(non_recipe_stems: frozenset[str]) -> list[dict[str, Any]]:
    """Build the capabilities[] block from docs/capabilities/<kind>/*.md frontmatter."""
    out: list[dict[str, Any]] = []
    for path in iter_files(CAPABILITY_GLOB, non_recipe_stems):
        text = path.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(text)
        if not fm or "id" not in fm or "kind" not in fm:
            # Non-capability markdown under docs/capabilities/ (e.g. a vector_db/README.md
            # that snuck past the non-recipe filter). Skip silently.
            continue
        entry: dict[str, Any] = OrderedDict()
        entry["id"] = fm["id"]
        entry["kind"] = fm["kind"]
        entry["path"] = str(path.relative_to(REPO_ROOT).as_posix())
        # v0.3 additions — the local-bringup track surface fields.
        if "layer" in fm:
            entry["layer"] = fm["layer"]
        if "requires" in fm:
            entry["requires"] = fm["requires"]
        if "bootstrap_inputs" in fm:
            entry["bootstrap_inputs"] = fm["bootstrap_inputs"]
        if "env_vars" in fm:
            entry["env_vars"] = fm["env_vars"]
        # Pull docker_service out of the nested docker block — it's the field
        # consumers (scaffold's plan-confirm panel, the compose-merge step)
        # need most often, and exposing it at the top level saves them a hop.
        docker = fm.get("docker")
        if isinstance(docker, dict) and "service" in docker:
            entry["docker_service"] = docker["service"]
        # Surface the host:container port bindings so consumers (and the
        # port-collision validator below) can detect two services contending
        # for the same host port without re-parsing the source markdown.
        if isinstance(docker, dict) and docker.get("ports"):
            entry["ports"] = list(docker["ports"])
        if fm.get("bootstrap_step"):
            entry["bootstrap_step"] = fm["bootstrap_step"]
        if fm.get("probe"):
            entry["probe"] = fm["probe"]
        if "provisioning_time" in fm:
            entry["provisioning_time"] = fm["provisioning_time"]
        if "cost_tier" in fm:
            entry["cost_tier"] = fm["cost_tier"]
        if "est_tokens" in fm:
            entry["est_tokens"] = fm["est_tokens"]
        if "card" in fm:
            entry["card"] = fm["card"]
        # Hybrid-intake discovery metadata (optional, additive).
        if "tags" in fm:
            entry["tags"] = fm["tags"]
        if "when_to_load" in fm:
            entry["when_to_load"] = fm["when_to_load"]
        # Port-typed registry fields (additive). `provides` is the canonical
        # capability-flag set the feature model references — revived here (it was
        # previously parsed but dropped). The rest land as adapters are migrated.
        if "provides" in fm:
            entry["provides"] = fm["provides"]
        if "implements" in fm:
            entry["implements"] = fm["implements"]
        if "excludes" in fm:
            entry["excludes"] = fm["excludes"]
        if "conflicts" in fm:
            entry["conflicts"] = fm["conflicts"]
        if "parameters" in fm:
            entry["parameters"] = fm["parameters"]
        if "verification" in fm:
            entry["verification"] = fm["verification"]
        # Derived, generation-oriented summary (no hand-authoring) — lets a
        # consumer inject a compact block instead of the full markdown body.
        entry["context_summary"] = _derive_context_summary(entry, fm)
        out.append(entry)
    out.sort(key=lambda e: e["id"])
    return out


def collect_frameworks(non_recipe_stems: frozenset[str]) -> list[dict[str, Any]]:
    """Build the frameworks[] block from docs/frameworks/*.md frontmatter."""
    out: list[dict[str, Any]] = []
    for path in iter_files(FRAMEWORK_GLOB, non_recipe_stems):
        text = path.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(text)
        if not fm or "id" not in fm or "language" not in fm:
            continue
        entry: dict[str, Any] = OrderedDict()
        entry["id"] = fm["id"]
        entry["language"] = fm["language"]
        entry["path"] = str(path.relative_to(REPO_ROOT).as_posix())
        if "package" in fm:
            entry["package"] = fm["package"]
        if "versions" in fm:
            entry["versions"] = fm["versions"]
        if "extra_packages" in fm:
            entry["extra_packages"] = fm["extra_packages"]
        # Hybrid-intake discovery metadata (optional, additive).
        if "tags" in fm:
            entry["tags"] = fm["tags"]
        if "when_to_load" in fm:
            entry["when_to_load"] = fm["when_to_load"]
        out.append(entry)
    out.sort(key=lambda e: e["id"])
    return out


def collect_ports(non_recipe_stems: frozenset[str]) -> list[dict[str, Any]]:
    """Build the ports[] block from docs/ports/*.md frontmatter.

    Ports are the abstract contracts adapters bind to (via ``implements:``);
    their protocol/concern values mirror the blueprints kernel IR
    (core/spec/ir.schema.json).
    """
    out: list[dict[str, Any]] = []
    for path in iter_files(PORT_GLOB, non_recipe_stems):
        text = path.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(text)
        if not fm or "id" not in fm:
            continue
        entry: dict[str, Any] = OrderedDict()
        entry["id"] = fm["id"]
        if "protocol" in fm:
            entry["protocol"] = fm["protocol"]
        if "concern" in fm:
            entry["concern"] = fm["concern"]
        entry["path"] = str(path.relative_to(REPO_ROOT).as_posix())
        for key in ("required", "cardinality", "default", "interface_version", "kinds", "adapter_home"):
            if key in fm:
                entry[key] = fm[key]
        out.append(entry)
    out.sort(key=lambda e: e["id"])
    return out


def validate_ports(ports: list[dict[str, Any]]) -> None:
    """Fail closed if a port's protocol/concern leaves the kernel IR vocabulary."""
    errors: list[str] = []
    for p in ports:
        proto, concern = p.get("protocol"), p.get("concern")
        if proto and proto not in PORT_PROTOCOLS:
            errors.append(f"port {p['id']}: protocol '{proto}' not in {sorted(PORT_PROTOCOLS)}")
        if concern and concern not in PORT_CONCERNS:
            errors.append(f"port {p['id']}: concern '{concern}' not in {sorted(PORT_CONCERNS)}")
        if proto and concern:
            errors.append(f"port {p['id']}: declares both protocol and concern; pick one")
    if errors:
        raise SystemExit("Port validation failed:\n  " + "\n  ".join(errors))


def build_compatibility(capabilities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Denormalize per-adapter edges into a flat, deterministic compatibility matrix.

    Edges: requires / excludes / conflicts from adapter fields, plus 'substitutes'
    for adapters that implement the same port (the same alternative-group). This is
    the feature-model data the scaffold resolver consumes; it is deliberately NOT
    compositions[] (the blueprints pattern x pattern matrix, a different namespace
    with a strict consumer Literal).
    """
    edges: list[dict[str, Any]] = []
    by_port: dict[str, list[str]] = {}
    for cap in capabilities:
        cid = cap["id"]
        impl = cap.get("implements") or {}
        port = impl.get("port")
        if port:
            by_port.setdefault(port, []).append(cid)
        for dep in cap.get("requires") or []:
            edges.append(OrderedDict([("a", cid), ("b", dep), ("relation", "requires")]))
        for ex in cap.get("excludes") or []:
            edges.append(OrderedDict([("a", cid), ("b", ex), ("relation", "excludes")]))
        for cf in cap.get("conflicts") or []:
            edges.append(OrderedDict([("a", cid), ("b", cf), ("relation", "conflicts")]))
    for port, ids in by_port.items():
        ordered = sorted(ids)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                edges.append(
                    OrderedDict(
                        [("a", ordered[i]), ("b", ordered[j]), ("relation", "substitutes"), ("via", f"port:{port}")]
                    )
                )
    edges.sort(key=lambda e: (e["a"], e["b"], e["relation"]))
    return edges


def derive_recipe_bindings(
    recipes: list[dict[str, Any]],
    capabilities: list[dict[str, Any]],
    ports: list[dict[str, Any]],
) -> None:
    """Derive each recipe's port -> adapter bindings from its capabilities[] and
    sanity-check the selection against the feature model (port cardinality).

    Additive: sets recipe['bindings']; authored fields are untouched. Cardinality
    violations warn (they do not fail the build) during the migration window.
    """
    cap_port = {c["id"]: (c.get("implements") or {}).get("port") for c in capabilities}
    port_card = {p["id"]: p.get("cardinality", "one") for p in ports}
    for r in recipes:
        grouped: dict[str, list[str]] = {}
        for cid in r.get("capabilities") or []:
            port = cap_port.get(cid)
            if port:
                grouped.setdefault(port, []).append(cid)
        if not grouped:
            continue
        for port, ids in grouped.items():
            if port_card.get(port) == "one" and len(ids) > 1:
                print(
                    f"warning: recipe '{r['slug']}': port '{port}' is exactly-one but binds {ids}",
                    file=sys.stderr,
                )
        r["bindings"] = OrderedDict(
            (port, ids[0] if (port_card.get(port) == "one" and len(ids) == 1) else sorted(ids))
            for port, ids in sorted(grouped.items())
        )


def fill_port_defaults(ports: list[dict[str, Any]], capabilities: list[dict[str, Any]]) -> None:
    """Auto-derive a port's default adapter when exactly one adapter implements it
    and no default is authored. Multi-adapter ports keep their authored default
    (or null — the suggestions layer recommends a default per combo)."""
    impls: dict[str, list[str]] = {}
    for c in capabilities:
        port = (c.get("implements") or {}).get("port")
        if port:
            impls.setdefault(port, []).append(c["id"])
    for p in ports:
        if p.get("default"):
            continue
        candidates = sorted(impls.get(p["id"], []))
        if len(candidates) == 1:
            p["default"] = candidates[0]


def _derive_context_summary(entry: dict[str, Any], fm: dict[str, Any]) -> str:
    """Derive a compact, generation-oriented capability summary from structured
    fields — no hand-authoring. Lets a consumer inject a few lines instead of the
    full markdown body when assembling LLM context. Pure function of the entry +
    frontmatter, so the catalog stays deterministic.
    """
    card = fm.get("card") if isinstance(fm.get("card"), dict) else {}
    name = (card.get("name") if card else None) or entry["id"]
    desc = str((card.get("description") if card else "") or "").strip()
    head = f"{name} ({entry['kind']})"
    if desc:
        head = f"{head} — {desc}"
    facts: list[str] = []
    if entry.get("env_vars"):
        facts.append("Env vars: " + ", ".join(entry["env_vars"]))
    docker = fm.get("docker")
    if entry.get("docker_service"):
        image = docker.get("image") if isinstance(docker, dict) else None
        facts.append(f"Docker service: {entry['docker_service']}" + (f" ({image})" if image else ""))
    if entry.get("bootstrap_step"):
        facts.append(f"Bootstrap: {entry['bootstrap_step']}")
    flags = entry.get("provides") or (card.get("capabilities_provided") if card else None)
    if flags:
        facts.append("Provides: " + ", ".join(flags))
    return head + ("\n" + ". ".join(facts) + "." if facts else "")


def _est_tokens(text: str) -> int:
    """Coarse whole-text token estimate (chars / 4), matching the consumer's
    own heuristic. Used only for the context_manifest budget hints."""
    return max(1, len(text) // 4)


def build_context_manifest(
    recipes: list[dict[str, Any]],
    capabilities: list[dict[str, Any]],
) -> None:
    """Emit each recipe's ``context_manifest``: the closed, pre-costed context
    set a consumer should load — the recipe's ``load_list`` projected to
    ``{path, required, cache_tier, when, est_tokens}`` (predicates kept symbolic,
    not pre-expanded) plus the resolved capability closure (the recipe's
    ``capabilities`` and their ``requires`` transitively).

    Additive + deterministic. A consumer that honours the manifest loads exactly
    these docs/capabilities and skips speculative discovery (prose-alias scans,
    transitive link walks). Per-doc ``est_tokens`` are filled only for docs that
    resolve to a local file; remote (blueprint-URL) docs carry no estimate.
    """
    cap_by_id = {c["id"]: c for c in capabilities}

    def _closure(ids: list[str]) -> list[str]:
        seen: OrderedDict[str, None] = OrderedDict()
        queue = list(ids)
        while queue:
            cid = queue.pop(0)
            if cid in seen or cid not in cap_by_id:
                continue
            seen[cid] = None
            for dep in cap_by_id[cid].get("requires") or []:
                if dep in cap_by_id and dep not in seen:
                    queue.append(dep)
        return list(seen)

    for r in recipes:
        recipe_dir = (REPO_ROOT / r["path"]).parent
        docs: list[dict[str, Any]] = []
        doc_tokens = 0
        for item in r.get("load_list") or []:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                continue
            path = item["path"]
            doc: dict[str, Any] = OrderedDict()
            doc["path"] = path
            doc["required"] = bool(item.get("required", True))
            if item.get("cache_tier"):
                doc["cache_tier"] = item["cache_tier"]
            if item.get("when"):
                doc["when"] = item["when"]
            if not path.startswith(("http://", "https://")):
                resolved = (recipe_dir / path).resolve()
                if resolved.is_file():
                    est = _est_tokens(resolved.read_text(encoding="utf-8"))
                    doc["est_tokens"] = est
                    doc_tokens += est
            docs.append(doc)
        cap_closure = _closure(list(r.get("capabilities") or []))
        if not docs and not cap_closure:
            continue
        est_total = doc_tokens
        if isinstance(r.get("est_tokens"), int):
            est_total += r["est_tokens"]
        for cid in cap_closure:
            cap = cap_by_id.get(cid)
            if cap and isinstance(cap.get("est_tokens"), int):
                est_total += cap["est_tokens"]
        manifest: dict[str, Any] = OrderedDict()
        manifest["docs"] = docs
        manifest["capabilities"] = cap_closure
        manifest["est_total_tokens"] = est_total
        r["context_manifest"] = manifest


def collect_path_only(glob: tuple[str, ...], non_recipe_stems: frozenset[str]) -> list[Any]:
    """Build a list of entries for stack[] / cross_cutting_docs[].

    Heterogeneous output:
      - Plain string ``"<path>"`` for docs without ``tags`` or ``when_to_load``
        in frontmatter — back-compat with consumers that read this block as
        ``list[str]``.
      - Mapping ``{path, tags?, when_to_load?}`` for docs that declare either
        discovery field. Lets the catalog surface the hybrid-intake metadata
        without forcing a wholesale shape migration.

    The list is sorted by path so the output is deterministic regardless of
    which entries are strings vs mappings.
    """
    out: list[Any] = []
    for p in iter_files(glob, non_recipe_stems):
        rel = str(p.relative_to(REPO_ROOT).as_posix())
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            out.append(rel)
            continue
        fm, _ = parse_frontmatter(text)
        if isinstance(fm, dict) and ("tags" in fm or "when_to_load" in fm):
            entry: dict[str, Any] = OrderedDict()
            entry["path"] = rel
            if "tags" in fm:
                entry["tags"] = fm["tags"]
            if "when_to_load" in fm:
                entry["when_to_load"] = fm["when_to_load"]
            out.append(entry)
        else:
            out.append(rel)
    out.sort(key=lambda e: e["path"] if isinstance(e, dict) else e)
    return out


def collect_pattern_docs(blueprints_catalog: dict[str, Any]) -> list[str]:
    """Enumerate blueprint cohort overviews for the catalog's
    ``pattern_docs[]``, ``primitive_docs[]``, and ``modifier_docs[]`` lists.

    Derives one flat sorted list of GitHub URLs from the reference catalog's
    four cohort blocks (``patterns``, ``workflows``, ``primitives``,
    ``modifiers``); callers bucket the result into per-cohort fields. Used by
    scaffold's alias resolver to convert prose mentions ("ReAct", "memory", …)
    to a blueprint doc URL, which scaffold resolves against its own fetched
    blueprints checkout.
    """
    out: list[str] = []
    for cohort in ("patterns", "workflows", "primitives", "modifiers"):
        for entry in blueprints_catalog.get(cohort) or []:
            tier_files = entry.get("tier_files") or {}
            overview = tier_files.get("overview")
            if not overview:
                d = entry.get("dir")
                overview = f"{d}/overview.md" if d else None
            if overview:
                out.append(BLUEPRINTS_DOC_URL_BASE + overview)
    return sorted(set(out))


def _host_port(binding: Any) -> str | None:
    """Return the host side of a ``"HOST:CONTAINER"`` docker port binding, or
    None when the binding doesn't name a host port (container-only form)."""
    if not isinstance(binding, str) or ":" not in binding:
        return None
    return binding.split(":", 1)[0].strip() or None


def _resolve_capability_stack(
    declared: list[str], cap_requires: dict[str, list[str]]
) -> list[str]:
    """Expand a recipe's declared capability ids to include transitive
    ``requires`` dependencies — the full service set ``docker compose up``
    brings online, which is what must be checked for host-port collisions."""
    seen: set[str] = set()
    stack: list[str] = []
    queue = list(declared)
    while queue:
        cid = queue.pop()
        if cid in seen:
            continue
        seen.add(cid)
        stack.append(cid)
        for dep in cap_requires.get(cid, []):
            if dep not in seen:
                queue.append(dep)
    return stack


def validate_recipe_references(
    recipes: list[dict[str, Any]],
    capabilities: list[dict[str, Any]],
    blueprints_catalog: dict[str, Any],
    *,
    stack_paths: set[str] | None = None,
    allow_missing_required: bool = False,
) -> None:
    """Raise SystemExit if any recipe / capability reference doesn't resolve.

    Checks ``agent_pattern`` against ``catalog.patterns[].id``, each
    ``primitives[]`` / ``modifiers[]`` entry against the matching cohort, each
    ``capabilities[]`` id against the locally-discovered capability files, and
    each capability's ``layer`` / ``requires`` / ``card`` / ``cost_tier``
    against the v0.3 contract. Also validates recipe-side v0.3 fields:
    ``runtime_modes`` (each swap's from/to resolves), ``smoke_test``
    (all three keys), ``cost_profile`` (tier + sources). Surfaces bad ids
    at generator time instead of at scaffold runtime.

    With ``allow_missing_required=True``, missing v0.3 required fields are
    downgraded to warnings on stderr — used during the migration window
    while capability + recipe content catches up to the schema. Reference
    resolution errors still fail loud.
    """
    cap_ids = {c["id"] for c in capabilities if "id" in c}
    cap_docker_services = {
        c["docker_service"] for c in capabilities if c.get("docker_service")
    }
    cap_ports = {c["id"]: (c.get("ports") or []) for c in capabilities if "id" in c}
    cap_requires = {c["id"]: (c.get("requires") or []) for c in capabilities if "id" in c}
    cohort_ids = {
        cohort: {e["id"] for e in (blueprints_catalog.get(cohort) or []) if "id" in e}
        for cohort in ("patterns", "primitives", "modifiers")
    }
    stack_paths = stack_paths or set()

    def _resolve_swap_target(value: str) -> bool:
        """A swap from/to is either a capability id or a stack-doc path of the
        form ``stack/<id>``."""
        if value in cap_ids:
            return True
        if value.startswith("stack/"):
            # Match against the collected stack[] paths (which are
            # docs/stack/<id>.md). Accept either "stack/<id>" or the full path.
            slug = value[len("stack/"):]
            return any(p.endswith(f"docs/stack/{slug}.md") for p in stack_paths)
        return False

    errors: list[str] = []
    soft_errors: list[str] = []

    # --- Recipe-side ---------------------------------------------------
    for r in recipes:
        path = r.get("path", "<unknown>")
        ap = r.get("agent_pattern")
        if ap and ap not in cohort_ids["patterns"]:
            errors.append(f"{path}: agent_pattern={ap!r} not in catalog.patterns[]")
        for prim in r.get("primitives") or []:
            if prim not in cohort_ids["primitives"]:
                errors.append(f"{path}: primitives[] {prim!r} not in catalog.primitives[]")
        for mod in r.get("modifiers") or []:
            if mod not in cohort_ids["modifiers"]:
                errors.append(f"{path}: modifiers[] {mod!r} not in catalog.modifiers[]")
        for cap in r.get("capabilities") or []:
            if cap not in cap_ids:
                errors.append(f"{path}: capabilities[] {cap!r} has no docs/capabilities/ entry")
        # Topology must be one of the canonical SCHEMA.md values (the scaffold's
        # Topology enum mirrors the same list). Absent is allowed — the consumer
        # infers a default. A bad value here would otherwise silently mis-model
        # the recipe downstream.
        topology = r.get("topology")
        if topology is not None and topology not in VALID_TOPOLOGIES:
            errors.append(
                f"{path}: topology={topology!r} must be one of {sorted(VALID_TOPOLOGIES)}"
            )
        # required_files must name a recognized backend entry point. Run
        # discovers the entry by basename (steps/launch_backend.py), so a recipe
        # that ships application source but lists no entry point can pass every
        # generation check yet SKIP/FAIL at launch. Empty required_files is left
        # to the v0.3 completeness checks elsewhere; this fires only once a
        # recipe declares files at all.
        required_files = r.get("required_files") or []
        if isinstance(required_files, list) and required_files:
            has_entry = any(
                isinstance(f, str) and f.rsplit("/", 1)[-1] in ENTRY_POINT_BASENAMES
                for f in required_files
            )
            if not has_entry:
                errors.append(
                    f"{path}: required_files names no recognized entry point "
                    f"(one of {sorted(ENTRY_POINT_BASENAMES)}) — run cannot launch it"
                )
        # No two compose services in the recipe's resolved capability stack may
        # bind the same host port (the project-layout port-allocation contract).
        # The app itself claims env_overrides.APP_PORT (default 8000).
        declared_caps = [c for c in (r.get("capabilities") or []) if c in cap_ids]
        stack = _resolve_capability_stack(declared_caps, cap_requires)
        app_port = str((r.get("env_overrides") or {}).get("APP_PORT", "8000"))
        host_ports: dict[str, list[str]] = {app_port: ["app"]}
        for cid in stack:
            for binding in cap_ports.get(cid, []):
                hp = _host_port(binding)
                if hp is not None:
                    host_ports.setdefault(hp, []).append(cid)
        for hp, owners in sorted(host_ports.items()):
            if len(owners) > 1:
                errors.append(
                    f"{path}: host port {hp} is bound by multiple services in the "
                    f"resolved stack: {', '.join(sorted(owners))}"
                )
        # v0.3 local-bringup contract.
        rmodes = r.get("runtime_modes")
        if rmodes is None:
            soft_errors.append(f"{path}: missing required field 'runtime_modes' (v0.3)")
        else:
            if not isinstance(rmodes, dict) or "default" not in rmodes:
                errors.append(f"{path}: runtime_modes must be a map containing a 'default' mode")
            else:
                for mode_name, mode_body in rmodes.items():
                    if not isinstance(mode_body, dict):
                        errors.append(f"{path}: runtime_modes.{mode_name} must be a mapping")
                        continue
                    swaps = mode_body.get("swaps") or {}
                    if not isinstance(swaps, dict):
                        errors.append(f"{path}: runtime_modes.{mode_name}.swaps must be a mapping")
                        continue
                    for src, dst in swaps.items():
                        if not _resolve_swap_target(str(src)):
                            errors.append(
                                f"{path}: runtime_modes.{mode_name}.swaps from-id {src!r} doesn't resolve"
                            )
                        if not _resolve_swap_target(str(dst)):
                            errors.append(
                                f"{path}: runtime_modes.{mode_name}.swaps to-id {dst!r} doesn't resolve"
                            )
                    # Optional context_budget — positive integers when present.
                    cb = mode_body.get("context_budget")
                    if cb is not None:
                        if not isinstance(cb, dict):
                            errors.append(
                                f"{path}: runtime_modes.{mode_name}.context_budget must be a mapping"
                            )
                        else:
                            for key in ("input_max", "output_max"):
                                val = cb.get(key)
                                if not isinstance(val, int) or isinstance(val, bool) or val <= 0:
                                    errors.append(
                                        f"{path}: runtime_modes.{mode_name}.context_budget.{key} "
                                        f"must be a positive integer"
                                    )
        # Optional cache_tier on each load_list entry — enum check only.
        # Path-based defaults are applied in collect_recipes; this catches
        # hand-authored invalid values.
        load_list = r.get("load_list") or []
        recipe_dir = (REPO_ROOT / path).parent if path != "<unknown>" else None
        if isinstance(load_list, list):
            for i, item in enumerate(load_list):
                if not isinstance(item, dict):
                    continue
                ct = item.get("cache_tier")
                if ct is not None and ct not in VALID_CACHE_TIERS:
                    errors.append(
                        f"{path}: load_list[{i}].cache_tier={ct!r} must be one of "
                        f"{sorted(VALID_CACHE_TIERS)}"
                    )
                _validate_load_list_predicate(
                    item.get("when"), f"{path}: load_list[{i}].when", cap_ids, errors
                )
                # Every load_list path must resolve to a file on disk. The
                # scaffold consumer fails open (loads what it can, warns on the
                # rest), so the producer is the only place a dead load-list link
                # gets caught — fail CLOSED here. Paths are recipe-relative.
                rel = item.get("path")
                if recipe_dir is not None and isinstance(rel, str) and rel:
                    # Blueprint docs are referenced as GitHub URLs (no vendoring);
                    # the consumer resolves them against its own blueprints checkout,
                    # so skip the on-disk check for them. Local paths still fail closed.
                    is_blueprint_url = rel.startswith("https://") and "/agent-blueprints/" in rel
                    if not is_blueprint_url and not (recipe_dir / rel).resolve().exists():
                        errors.append(
                            f"{path}: load_list[{i}].path {rel!r} does not resolve "
                            f"to a file on disk"
                        )
        # acceptance_contracts: shape-validated when present; PRESENCE of the
        # block and all four sub-keys is mandatory for validated recipes
        # (declared emptiness is fine; silence is not).
        ac = r.get("acceptance_contracts")
        is_validated = "validated" in str(r.get("status") or "").lower()
        if ac is None:
            msg = f"{path}: missing 'acceptance_contracts'"
            if is_validated:
                errors.append(msg + " — mandatory for 'Blueprint (validated)' recipes")
            else:
                soft_errors.append(msg + " (mandatory once the recipe flips to validated)")
        elif is_validated and isinstance(ac, dict):
            for block in ACCEPTANCE_CONTRACT_BLOCKS:
                if block not in ac:
                    errors.append(
                        f"{path}: acceptance_contracts.{block} must be declared "
                        f"(an explicit empty list is allowed) on validated recipes"
                    )
        _validate_acceptance_contracts(r, cap_ids, cap_docker_services, errors)
        smoke = r.get("smoke_test")
        if smoke is None:
            soft_errors.append(f"{path}: missing required field 'smoke_test' (v0.3)")
        elif not isinstance(smoke, dict) or not all(
            k in smoke and isinstance(smoke[k], str) and smoke[k].strip()
            for k in ("ready", "exercise", "assert_jq")
        ):
            errors.append(
                f"{path}: smoke_test must be a mapping with non-empty 'ready', 'exercise', 'assert_jq'"
            )
        cost = r.get("cost_profile")
        if cost is None:
            soft_errors.append(f"{path}: missing required field 'cost_profile' (v0.3)")
        elif not isinstance(cost, dict):
            errors.append(f"{path}: cost_profile must be a mapping")
        else:
            tier = cost.get("tier")
            if tier not in VALID_RECIPE_COST_TIERS:
                errors.append(
                    f"{path}: cost_profile.tier={tier!r} must be one of {sorted(VALID_RECIPE_COST_TIERS)}"
                )
            if not isinstance(cost.get("sources"), list):
                errors.append(f"{path}: cost_profile.sources must be a list")

    # --- Capability-side -----------------------------------------------
    for c in capabilities:
        path = c.get("path", "<unknown>")
        # kind drives the consumer's resolver bucket + id-prefix convention.
        # The consumer carries an unknown kind as `unresolved`; the producer
        # fails closed so a typo'd kind never ships in the catalog.
        kind = c.get("kind")
        if kind is not None and kind not in VALID_CAPABILITY_KINDS:
            errors.append(
                f"{path}: kind={kind!r} must be one of {sorted(VALID_CAPABILITY_KINDS)}"
            )
        layer = c.get("layer")
        if layer is None:
            soft_errors.append(f"{path}: missing required field 'layer' (v0.3)")
        elif layer not in LAYER_IDS:
            errors.append(f"{path}: layer={layer!r} not in catalog.LAYER_ORDER")
        for dep in c.get("requires") or []:
            if dep not in cap_ids:
                errors.append(f"{path}: requires {dep!r} has no docs/capabilities/ entry")
        card = c.get("card")
        if card is None:
            soft_errors.append(f"{path}: missing required field 'card' (v0.3)")
        elif not isinstance(card, dict):
            errors.append(f"{path}: card must be a mapping")
        else:
            for required_key in ("name", "description"):
                if not card.get(required_key):
                    errors.append(f"{path}: card.{required_key} must be a non-empty string")
        ct = c.get("cost_tier")
        if ct is None:
            soft_errors.append(f"{path}: missing required field 'cost_tier' (v0.3)")
        elif ct not in VALID_COST_TIERS:
            errors.append(
                f"{path}: cost_tier={ct!r} must be one of {sorted(VALID_COST_TIERS)}"
            )

    if soft_errors and not allow_missing_required:
        # Treat soft errors as hard when the flag is not set.
        errors.extend(soft_errors)
    elif soft_errors:
        for msg in soft_errors:
            print(f"warning: {msg}", file=sys.stderr)

    if errors:
        raise SystemExit("error: catalog validation failed:\n  - " + "\n  - ".join(errors))


def report_content_warnings(
    recipes: list[dict[str, Any]],
    capabilities: list[dict[str, Any]],
    frameworks: list[dict[str, Any]],
    blueprints_catalog: dict[str, Any],
) -> list[str]:
    """Advisory content-drift checks. These never fail the build — they are
    coverage gaps and soft inconsistencies, not contract violations. Returns the
    warning messages (also printed to stderr) so callers / tests can inspect them.

    1. Advertisement coherence — a provider named in a recipe's runtime_modes
       descriptions (openai / cohere / qdrant / …) should be backed by a
       capability and a dependency. Unbacked => the advertised stack can't run.
    2. Orphan blueprints — a blueprint pattern that no recipe selects via
       agent_pattern (a coverage gap; the pattern ships with no runnable recipe).
    3. Orphan frameworks — a framework doc that no recipe references in its
       load_list.
    """
    warnings: list[str] = []

    for r in recipes:
        path = r.get("path", "<unknown>")
        caps = r.get("capabilities") or []
        deps = r.get("recipe_dependencies") or {}
        dep_names = [
            str(name).lower()
            for lang in deps.values()
            if isinstance(lang, dict)
            for name in lang
        ]
        rmodes = r.get("runtime_modes") or {}
        desc = " ".join(
            str(m.get("description", ""))
            for m in rmodes.values()
            if isinstance(m, dict)
        ).lower()
        for token, (cap_sub, dep_sub) in sorted(ADVERTISED_PROVIDERS.items()):
            if token not in desc:
                continue
            cap_backed = any(cap_sub in c for c in caps)
            dep_backed = any(dep_sub in d for d in dep_names)
            if not (cap_backed or dep_backed):
                warnings.append(
                    f"{path}: runtime_modes advertises {token!r} but no capability "
                    f"or dependency backs it — capabilities + recipe_dependencies "
                    f"should name it (or drop it from the description)"
                )

    used_patterns = {r.get("agent_pattern") for r in recipes if r.get("agent_pattern")}
    pattern_ids = {e["id"] for e in (blueprints_catalog.get("patterns") or []) if "id" in e}
    for orphan in sorted(pattern_ids - used_patterns):
        warnings.append(
            f"blueprint pattern {orphan!r} has no recipe (no agent_pattern selects it) "
            f"— coverage gap, not a first-run breaker"
        )

    referenced_frameworks: set[str] = set()
    for r in recipes:
        for item in r.get("load_list") or []:
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                rel = item["path"]
                if "/frameworks/" in rel:
                    referenced_frameworks.add(rel.rsplit("/", 1)[-1])
    for fw in frameworks:
        if not isinstance(fw, dict):
            continue
        fw_path = fw.get("path")
        if not isinstance(fw_path, str):
            continue
        basename = fw_path.rsplit("/", 1)[-1]
        if basename not in referenced_frameworks:
            warnings.append(
                f"framework {fw.get('id', basename)!r} is referenced by no recipe "
                f"load_list — coverage gap, not a first-run breaker"
            )

    for msg in warnings:
        print(f"warning: {msg}", file=sys.stderr)
    return warnings


def _validate_load_list_predicate(
    predicate: Any,
    label: str,
    cap_ids: set[str],
    errors: list[str],
) -> None:
    """Hard-fail on any ``when`` predicate the consumer grammar can't parse.

    The scaffold's evaluator is fail-open (a malformed predicate loads the
    doc rather than dropping it), so the only place a typo can be caught
    before it silently degrades context selection is here, at catalog build.
    ``capabilities contains`` ids must also resolve — a predicate gated on a
    capability that doesn't exist would never fire.
    """
    if predicate is None:
        return
    if not isinstance(predicate, str) or not predicate.strip():
        errors.append(f"{label} must be a non-empty string when present")
        return
    if LOAD_LIST_PRED_EQ_RE.match(predicate):
        return
    m = LOAD_LIST_PRED_CONTAINS_RE.match(predicate)
    if m is not None:
        cap_id = m.group(1)
        if cap_id not in cap_ids:
            errors.append(
                f"{label}: 'capabilities contains' references unknown capability {cap_id!r}"
            )
        return
    errors.append(
        f"{label}: unparseable predicate {predicate!r} — grammar is "
        f"\"<language|framework|topology> == '<value>'\" or "
        f"\"capabilities contains '<cap.id>'\" (see docs/recipes/SCHEMA.md)"
    )


def validate_required_env_against_contract(recipes: list[dict[str, Any]]) -> None:
    """Cross-check ``acceptance_contracts.required_env`` against the derived
    ``env_contract``.

    Runs AFTER :func:`derive_env_contracts`. Every capability-sourced
    required_env entry (``source: capability:<id>``) must appear in the
    recipe's derived env_contract — a mismatch means the acceptance contract
    promises an env var the capability layer never declares, which a consumer
    can neither prompt for nor pre-flight. Prompted / recipe-local sources
    are exempt (they're recipe-specific by definition).
    """
    errors: list[str] = []
    for r in recipes:
        path = r.get("path", "<unknown>")
        ac = r.get("acceptance_contracts")
        if not isinstance(ac, dict):
            continue
        required_env = ac.get("required_env")
        if not isinstance(required_env, list):
            continue
        contract_names = {
            str(e.get("name", "")).upper()
            for e in (r.get("env_contract") or [])
            if isinstance(e, dict)
        }
        for i, ev in enumerate(required_env):
            if not isinstance(ev, dict):
                continue
            name = str(ev.get("name", "") or "")
            source = str(ev.get("source", "") or "")
            if not name or not source.startswith("capability:"):
                continue
            if name.upper() not in contract_names:
                errors.append(
                    f"{path}: acceptance_contracts.required_env[{i}] {name!r} "
                    f"(source {source!r}) is not in the derived env_contract — "
                    f"the capability doesn't declare it"
                )
    if errors:
        raise SystemExit(
            "error: required_env/env_contract cross-check failed:\n  - " + "\n  - ".join(errors)
        )


def _validate_acceptance_contracts(
    recipe: dict[str, Any],
    cap_ids: set[str],
    cap_docker_services: set[str],
    errors: list[str],
) -> None:
    """Validate the optional ``acceptance_contracts`` block on a recipe.

    Block shape (every key optional, but enforced when present):

      acceptance_contracts:
        http_endpoints:
          - {path: /health, method: GET, status: 200}
        required_env:
          - {name: ANTHROPIC_API_KEY, source: prompted}
          - {name: DATABASE_URL,      source: capability:relational.postgres}
        required_compose_services: [postgres, redis]
        smoke_assertions:
          - {jq: ".answer | length > 0", against: smoke_test.exercise.stdout}

    Rules:
      - ``http_endpoints[].path`` must be a string starting with ``/``.
      - ``required_env[].source`` of the form ``capability:<id>`` must
        resolve to a declared capability id.
      - ``required_compose_services`` entries must match some capability's
        ``docker_service``.
      - ``smoke_assertions[].jq`` must be a non-empty string.
    """
    ac = recipe.get("acceptance_contracts")
    if ac is None:
        return
    path = recipe.get("path", "<unknown>")
    if not isinstance(ac, dict):
        errors.append(f"{path}: acceptance_contracts must be a mapping")
        return

    endpoints = ac.get("http_endpoints")
    if endpoints is not None:
        if not isinstance(endpoints, list):
            errors.append(f"{path}: acceptance_contracts.http_endpoints must be a list")
        else:
            for i, ep in enumerate(endpoints):
                if not isinstance(ep, dict):
                    errors.append(
                        f"{path}: acceptance_contracts.http_endpoints[{i}] must be a mapping"
                    )
                    continue
                ep_path = ep.get("path")
                if not isinstance(ep_path, str) or not ep_path.startswith("/"):
                    errors.append(
                        f"{path}: acceptance_contracts.http_endpoints[{i}].path must "
                        f"be a string starting with '/'"
                    )

    required_env = ac.get("required_env")
    if required_env is not None:
        if not isinstance(required_env, list):
            errors.append(f"{path}: acceptance_contracts.required_env must be a list")
        else:
            for i, ev in enumerate(required_env):
                if not isinstance(ev, dict):
                    errors.append(
                        f"{path}: acceptance_contracts.required_env[{i}] must be a mapping"
                    )
                    continue
                src = ev.get("source", "")
                if isinstance(src, str) and src.startswith("capability:"):
                    cap_id = src[len("capability:"):]
                    if cap_id not in cap_ids:
                        errors.append(
                            f"{path}: acceptance_contracts.required_env[{i}].source "
                            f"references unknown capability {cap_id!r}"
                        )

    required_services = ac.get("required_compose_services")
    if required_services is not None:
        if not isinstance(required_services, list):
            errors.append(
                f"{path}: acceptance_contracts.required_compose_services must be a list"
            )
        else:
            for svc in required_services:
                if not isinstance(svc, str):
                    errors.append(
                        f"{path}: acceptance_contracts.required_compose_services "
                        f"entries must be strings"
                    )
                    continue
                if svc not in cap_docker_services:
                    errors.append(
                        f"{path}: acceptance_contracts.required_compose_services "
                        f"{svc!r} not present in any capability's docker_service"
                    )

    smoke_assertions = ac.get("smoke_assertions")
    if smoke_assertions is not None:
        if not isinstance(smoke_assertions, list):
            errors.append(
                f"{path}: acceptance_contracts.smoke_assertions must be a list"
            )
        else:
            for i, sa in enumerate(smoke_assertions):
                if not isinstance(sa, dict):
                    errors.append(
                        f"{path}: acceptance_contracts.smoke_assertions[{i}] must be a mapping"
                    )
                    continue
                jq_expr = sa.get("jq")
                if not isinstance(jq_expr, str) or not jq_expr.strip():
                    errors.append(
                        f"{path}: acceptance_contracts.smoke_assertions[{i}].jq "
                        f"must be a non-empty string"
                    )


# ---------------------------------------------------------------------------
# env_contract derivation + suggestions cohort
# ---------------------------------------------------------------------------


def derive_env_contracts(
    recipes: list[dict[str, Any]],
    capabilities: list[dict[str, Any]],
) -> None:
    """Mutate each recipe entry to add an ``env_contract`` block derived from
    the recipe's selected ``capabilities[]``.

    For every recipe with a `capabilities[]` list, walks each referenced
    capability, collects ``env_vars``, dedupes case-insensitively (first
    declaration wins) and annotates with source-capability + any default the
    recipe's ``env_overrides`` declares.

    The emitted block shape:

        env_contract:
          - {name: POSTGRES_USER, source_capability: relational.postgres}
          - {name: REDIS_URL,     source_capability: cache.redis}
          - {name: APP_PORT,      source_capability: <recipe>, default: 8000}
    """
    cap_by_id = {c["id"]: c for c in capabilities if "id" in c}
    for r in recipes:
        cap_ids = r.get("capabilities") or []
        overrides = r.get("env_overrides") or {}
        seen: dict[str, str] = {}
        contract: list[dict[str, Any]] = []
        for cap_id in cap_ids:
            cap = cap_by_id.get(cap_id)
            if not cap:
                continue
            for var in cap.get("env_vars") or []:
                key = var.upper()
                if key in seen:
                    continue
                entry: dict[str, Any] = OrderedDict()
                entry["name"] = var
                entry["source_capability"] = cap_id
                if var in overrides:
                    entry["default"] = overrides[var]
                contract.append(entry)
                seen[key] = cap_id
        for var, default in overrides.items():
            key = var.upper()
            if key in seen:
                continue
            entry = OrderedDict()
            entry["name"] = var
            entry["source_capability"] = r["slug"]
            entry["default"] = default
            contract.append(entry)
            seen[key] = r["slug"]
        if contract:
            r["env_contract"] = contract


def collect_suggestions() -> dict[str, Any]:
    """Build the catalog.suggestions block from docs/suggestions/<version>/*.md.

    Exactly one ``<version>/`` directory may exist on disk at any time. The
    generator raises if more than one is present (the sync workflow's purge
    step enforces this in CI). Returns an empty payload if no version dir
    exists yet (the post-purge waiting state).
    """
    out: dict[str, Any] = OrderedDict()
    out["blueprints_version"] = None
    out["description"] = (
        "Per-combo stack recommendations scoped to the upstream blueprints "
        "version pinned in reference/blueprints/patterns-catalog.yaml. One file "
        "per pattern × primitives × modifiers combination."
    )
    readme_candidate = SUGGESTIONS_ROOT / "README.md"
    if readme_candidate.is_file():
        out["readme_path"] = str(readme_candidate.relative_to(REPO_ROOT).as_posix())
    out["combos"] = []
    if not SUGGESTIONS_ROOT.is_dir():
        return out
    version_dirs = sorted(
        p for p in SUGGESTIONS_ROOT.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )
    if not version_dirs:
        return out
    if len(version_dirs) > 1:
        raise SystemExit(
            "error: docs/suggestions/ contains multiple version directories: "
            f"{[p.name for p in version_dirs]}. Only the latest blueprints "
            "version's suggestions may exist on disk (sync-blueprints.yml "
            "should have purged the older one)."
        )
    version_dir = version_dirs[0]
    version = version_dir.name
    out["blueprints_version"] = version
    out["description"] = (
        f"Per-combo stack recommendations scoped to upstream blueprints "
        f"version {version}. One file per pattern × primitives × modifiers "
        f"combination."
    )
    combos: list[dict[str, Any]] = []
    for path in sorted(version_dir.glob("*.md")):
        if path.stem.lower() in ("readme", "schema"):
            continue
        text = path.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(text)
        if not fm:
            continue
        if fm.get("blueprints_version") != version:
            raise SystemExit(
                f"error: {path.relative_to(REPO_ROOT)}: blueprints_version="
                f"{fm.get('blueprints_version')!r} doesn't match directory name {version!r}."
            )
        entry: dict[str, Any] = OrderedDict()
        entry["applies_to"] = fm.get("applies_to") or {}
        entry["path"] = str(path.relative_to(REPO_ROOT).as_posix())
        if "recommends" in fm:
            entry["recommends"] = fm["recommends"]
        if "local_only_swaps" in fm:
            entry["local_only_swaps"] = fm["local_only_swaps"]
        if "est_tokens" in fm:
            entry["est_tokens"] = fm["est_tokens"]
        combos.append(entry)
    out["combos"] = combos
    return out


# ---------------------------------------------------------------------------
# Blueprints fetch
# ---------------------------------------------------------------------------


def fetch_text(url: str) -> str:
    """Fetch raw text from an http(s) or file URL.

    Supports ``file://`` URLs and bare local paths so local dev can point at
    a working-copy blueprints catalog without spinning up a webserver.
    """
    if url.startswith("file://") or url.startswith("/") or url.startswith("./"):
        path = url[7:] if url.startswith("file://") else url
        return Path(path).read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers={"Accept": "text/yaml, text/plain, */*"})
    with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT_SECONDS) as resp:
        return resp.read().decode("utf-8")


def load_blueprints_catalog(url: str) -> dict[str, Any]:
    """Fetch + parse the blueprints catalog. Raises on any failure."""
    try:
        text = fetch_text(url)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        raise SystemExit(
            f"error: failed to fetch blueprints catalog from {url}: {exc}\n"
            "Pass --blueprints-catalog-url to point at a local file or a different URL "
            "while iterating."
        ) from exc
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SystemExit(f"error: blueprints catalog at {url} is not valid YAML: {exc}") from exc
    if not isinstance(loaded, dict):
        raise SystemExit(f"error: blueprints catalog at {url} did not parse as a mapping")
    return loaded


# ---------------------------------------------------------------------------
# Assemble + emit
# ---------------------------------------------------------------------------


def build_catalog(
    seed: dict[str, Any],
    blueprints_catalog: dict[str, Any],
    blueprints_repo: str,
    blueprints_branch: str,
    *,
    allow_missing_required: bool = False,
) -> dict[str, Any]:
    non_recipe_stems = frozenset(
        s.lower() for s in seed.get("non_recipe_stems", list(DEFAULT_NON_RECIPE_STEMS))
    )
    catalog: dict[str, Any] = OrderedDict()
    catalog["schema_version"] = SCHEMA_VERSION
    catalog["generator_version"] = GENERATOR_VERSION
    catalog["contract_version"] = CONTRACT_VERSION

    # Bootstrap-sequencing contract — every capability's `layer:` must be one
    # of these layer ids. Consumers walk this list top-to-bottom when running
    # `docker compose up + bootstrap`.
    catalog["LAYER_ORDER"] = [
        OrderedDict([("id", layer_id), ("description", desc)])
        for layer_id, desc in LAYER_ORDER
    ]

    # Blueprints pointer block — the dependency declaration this repo makes
    # explicit so downstream consumers (scaffold) never reach into blueprints
    # by name. Deliberately no `catalog_url` or `upstream_sha` fields: those
    # are environment-dependent and would make the drift check flap.
    # Version tracking happens implicitly via the embedded patterns[] /
    # compositions[] content — blueprints changes show up as catalog content
    # diffs.
    blueprints_block: dict[str, Any] = OrderedDict()
    blueprints_block["repo"] = blueprints_repo
    blueprints_block["branch"] = blueprints_branch
    blueprints_block["catalog_path"] = "patterns-catalog.yaml"
    # URL pattern + directory entry: scaffold uses these to resolve recipe-body
    # links of the form `github.com/.../agent-blueprints/...` to local paths
    # in the fetched blueprints tree, without hardcoding the convention itself.
    blueprints_block["url_pattern"] = "https://github.com/{repo}/(?:tree|blob|raw)/{branch}/{path}"
    blueprints_block["directory_entry"] = "overview.md"
    catalog["blueprints"] = blueprints_block

    # Embedded blueprints index. Pass-through; we don't restructure.
    # Upstream taxonomy v2 ships four cohort blocks (patterns, workflows,
    # primitives, modifiers) plus compositions; all are forwarded verbatim.
    # workflows[] is a derived view of patterns[] where category=workflow and
    # will be removed in upstream taxonomy v3 — preserved here for compat.
    catalog["patterns"] = blueprints_catalog.get("patterns") or []
    catalog["workflows"] = blueprints_catalog.get("workflows") or []
    catalog["primitives"] = blueprints_catalog.get("primitives") or []
    catalog["modifiers"] = blueprints_catalog.get("modifiers") or []
    catalog["compositions"] = blueprints_catalog.get("compositions") or []

    # This repo's own content.
    catalog["recipes"] = collect_recipes(non_recipe_stems)
    catalog["capabilities"] = collect_capabilities(non_recipe_stems)
    catalog["ports"] = collect_ports(non_recipe_stems)
    validate_ports(catalog["ports"])
    fill_port_defaults(catalog["ports"], catalog["capabilities"])
    catalog["compatibility"] = build_compatibility(catalog["capabilities"])
    derive_recipe_bindings(catalog["recipes"], catalog["capabilities"], catalog["ports"])
    build_context_manifest(catalog["recipes"], catalog["capabilities"])
    catalog["frameworks"] = collect_frameworks(non_recipe_stems)
    catalog["stack"] = collect_path_only(STACK_GLOB, non_recipe_stems)
    catalog["cross_cutting_docs"] = collect_path_only(CROSS_CUTTING_GLOB, non_recipe_stems)

    # Split the blueprint cohort overviews into per-cohort lists. Older
    # scaffold versions look for the flat pattern_docs[] (kept populated with
    # patterns + workflows for back-compat); newer consumers can use the more
    # granular siblings.
    all_overviews = collect_pattern_docs(blueprints_catalog)
    catalog["pattern_docs"] = sorted(
        p for p in all_overviews if "/patterns/" in p or "/workflows/" in p
    )
    catalog["primitive_docs"] = sorted(p for p in all_overviews if "/primitives/" in p)
    catalog["modifier_docs"] = sorted(p for p in all_overviews if "/modifiers/" in p)

    # Validate every recipe-side + capability-side id resolves before we
    # emit. Loud failure here is better than silent skip at scaffold runtime.
    # During the v0.3 migration window, allow_missing_required downgrades the
    # "missing required field" checks to warnings (resolution errors still
    # fail loud). Remove the flag use at end of the migration.
    # stack[] is heterogeneous (string or {path, tags?, when_to_load?}). Pull
    # the path strings only for swap-target resolution in the validator.
    stack_paths = {
        entry["path"] if isinstance(entry, dict) else entry
        for entry in catalog["stack"]
    }
    validate_recipe_references(
        catalog["recipes"],
        catalog["capabilities"],
        blueprints_catalog,
        stack_paths=stack_paths,
        allow_missing_required=allow_missing_required,
    )

    # Advisory drift checks — coverage gaps + soft inconsistencies. Printed to
    # stderr; never fail the build (orphans and stale advertisements are not
    # first-run breakers).
    report_content_warnings(
        catalog["recipes"],
        catalog["capabilities"],
        catalog["frameworks"],
        blueprints_catalog,
    )

    # Derive each recipe's env_contract from the dedup of its capabilities'
    # env_vars + the recipe's env_overrides. Runs after validation so we
    # never derive against an unresolved capability id.
    derive_env_contracts(catalog["recipes"], catalog["capabilities"])

    # Cross-check acceptance contracts against what was just derived: a
    # capability-sourced required_env entry that the capability layer never
    # declares is a contract the consumer cannot satisfy.
    validate_required_env_against_contract(catalog["recipes"])

    # Per-combo stack recommendations for the current upstream pin. Empty
    # block when no version dir exists yet (post-purge waiting state).
    catalog["suggestions"] = collect_suggestions()

    # Seeded behavior knobs.
    catalog["aliases"] = seed.get("aliases", {})
    catalog["cross_cutting"] = seed.get("cross_cutting", {})
    catalog["non_recipe_stems"] = sorted(non_recipe_stems)
    catalog["min_alias_length"] = seed.get("min_alias_length", 3)

    return catalog


# ---------------------------------------------------------------------------
# YAML emit with deterministic ordering
# ---------------------------------------------------------------------------


def _ordered_dict_representer(dumper: yaml.SafeDumper, data: OrderedDict) -> yaml.MappingNode:
    """Emit OrderedDict in insertion order — PyYAML 6.x sorts plain dicts by
    default unless sort_keys=False is passed, but OrderedDict needs an explicit
    representer so YAML safe-dump treats it as a mapping."""
    return dumper.represent_mapping("tag:yaml.org,2002:map", data.items())


def render_yaml(catalog: dict[str, Any]) -> str:
    yaml.SafeDumper.add_representer(OrderedDict, _ordered_dict_representer)
    return yaml.safe_dump(
        catalog,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=10000,
        indent=2,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "catalog.yaml"),
        help="Output path. Default: <repo-root>/catalog.yaml",
    )
    parser.add_argument(
        "--blueprints-catalog-url",
        default=DEFAULT_BLUEPRINTS_CATALOG_URL,
        help=f"URL to fetch the blueprints catalog from. Default: {DEFAULT_BLUEPRINTS_CATALOG_URL}",
    )
    parser.add_argument(
        "--blueprints-repo",
        default=DEFAULT_BLUEPRINTS_REPO,
        help=f"owner/repo for blueprints. Default: {DEFAULT_BLUEPRINTS_REPO}",
    )
    parser.add_argument(
        "--blueprints-branch",
        default=DEFAULT_BLUEPRINTS_BRANCH,
        help=f"Branch on the blueprints repo. Default: {DEFAULT_BLUEPRINTS_BRANCH}",
    )
    parser.add_argument(
        "--seed",
        default=str(REPO_ROOT / "scripts" / "_seed_aliases.yaml"),
        help="Path to the seed aliases / cross-cutting / non-recipe-stems YAML.",
    )
    parser.add_argument(
        "--allow-missing-required",
        action="store_true",
        help=(
            "Downgrade 'missing required v0.3 field' errors to warnings on stderr. "
            "Used during the migration window while capability + recipe content "
            "catches up to the schema. Reference-resolution errors still fail loud."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Validate content + verify the committed catalog.yaml is up to date "
            "without writing it. Exits non-zero on a validation failure or if "
            "regeneration would change --out. Use in CI / pre-commit."
        ),
    )
    args = parser.parse_args(argv)

    seed_path = Path(args.seed)
    if not seed_path.is_file():
        print(f"error: seed file not found at {seed_path}", file=sys.stderr)
        return 2
    seed = yaml.safe_load(seed_path.read_text(encoding="utf-8")) or {}

    blueprints_catalog = load_blueprints_catalog(args.blueprints_catalog_url)

    catalog = build_catalog(
        seed=seed,
        blueprints_catalog=blueprints_catalog,
        blueprints_repo=args.blueprints_repo,
        blueprints_branch=args.blueprints_branch,
        allow_missing_required=args.allow_missing_required,
    )

    body = render_yaml(catalog)
    header = (
        "# Auto-generated by scripts/generate_catalog.py — do not edit.\n"
        "# Edit source docs (their YAML frontmatter) or the upstream blueprints\n"
        "# catalog, then regenerate.\n"
    )
    content = header + body
    out_path = Path(args.out)

    if args.check:
        # Validation already ran inside build_catalog (hard failures raised
        # SystemExit before we got here). Now confirm the committed catalog
        # matches a fresh regeneration — without writing anything.
        if not out_path.is_file():
            print(f"error: --check: {out_path} does not exist", file=sys.stderr)
            return 1
        if out_path.read_text(encoding="utf-8") != content:
            print(
                f"error: --check: {out_path} is stale — regenerate with "
                "`python scripts/generate_catalog.py`",
                file=sys.stderr,
            )
            return 1
        print(f"ok: content validates and {out_path} is up to date")
        return 0

    out_path.write_text(content, encoding="utf-8")

    suggestions = catalog.get("suggestions") or {}
    suggestions_version = suggestions.get("blueprints_version") or "(empty)"
    suggestions_combos = len(suggestions.get("combos") or [])
    print(
        f"Wrote {args.out} "
        f"({len(catalog['recipes'])} recipes, "
        f"{len(catalog['capabilities'])} capabilities, "
        f"{len(catalog['frameworks'])} frameworks, "
        f"{len(catalog['patterns'])} patterns + "
        f"{len(catalog['primitives'])} primitives + "
        f"{len(catalog['modifiers'])} modifiers embedded, "
        f"{len(catalog['compositions'])} compositions, "
        f"suggestions={suggestions_version}/{suggestions_combos} combos)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
