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
2. Reads ``patterns-catalog.yaml`` from the **vendored snapshot** of
   agent-blueprints at ``vendored/blueprints/patterns-catalog.yaml``. The
   vendored tree is managed by ``vendir`` (see ``vendir.yml``). Extracts
   its ``patterns[]``, ``workflows[]``, and ``compositions[]`` blocks and
   embeds them. Override the source via ``--blueprints-catalog-url`` for
   local iteration against an unmerged blueprints branch.
3. Enumerates ``pattern_docs[]`` from the vendored tree:
   ``vendored/blueprints/patterns/<id>/overview.md`` (one per pattern) and
   ``vendored/blueprints/workflows/<id>/overview.md`` (one per workflow).
   The previous lighter mirror at ``docs/patterns/*.md`` has been retired.
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

    # Default: read from vendored/blueprints/patterns-catalog.yaml. To pull
    # newer upstream content, run `vendir sync` first.
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
GENERATOR_VERSION = "1.1.0"

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = REPO_ROOT / "docs"

VENDORED_BLUEPRINTS_DIR = REPO_ROOT / "vendored" / "blueprints"
DEFAULT_BLUEPRINTS_CATALOG_URL = str(VENDORED_BLUEPRINTS_DIR / "patterns-catalog.yaml")
"""Default source for the blueprints catalog. Reads the vendored snapshot at
``vendored/blueprints/patterns-catalog.yaml``. The vendored tree is managed
by ``vendir`` (see ``vendir.yml``). Override via ``--blueprints-catalog-url``
to point at a URL or a different local path when iterating against an
unmerged upstream branch."""

DEFAULT_BLUEPRINTS_REPO = "jagguvarma15/agent-blueprints"
DEFAULT_BLUEPRINTS_BRANCH = "main"

NETWORK_TIMEOUT_SECONDS = 10.0

# Source files for each section. Globs are relative to DOCS_ROOT.
RECIPE_GLOB = ("recipes", "*.md")
CAPABILITY_GLOB = ("capabilities", "*", "*.md")
FRAMEWORK_GLOB = ("frameworks", "*.md")
STACK_GLOB = ("stack", "*.md")
CROSS_CUTTING_GLOB = ("cross-cutting", "*.md")

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
        entry: dict[str, Any] = OrderedDict()
        entry["slug"] = path.stem
        entry["path"] = str(path.relative_to(REPO_ROOT).as_posix())
        entry["title"] = title
        # Pass-through fields in the order the scaffold's Recipe model expects.
        for key in (
            "status",
            "languages",
            "topology",
            "complexity",
            "agent_pattern",
            "required_files",
            "recipe_dependencies",
            "external_services",
            "capabilities",
            "bootstrap_config",
            "roles",
            "load_list",
        ):
            if key in fm:
                entry[key] = fm[key]
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
        if "env_vars" in fm:
            entry["env_vars"] = fm["env_vars"]
        # Pull docker_service out of the nested docker block — it's the field
        # consumers (scaffold's plan-confirm panel, the compose-merge step)
        # need most often, and exposing it at the top level saves them a hop.
        docker = fm.get("docker")
        if isinstance(docker, dict) and "service" in docker:
            entry["docker_service"] = docker["service"]
        if fm.get("bootstrap_step"):
            entry["bootstrap_step"] = fm["bootstrap_step"]
        if fm.get("probe"):
            entry["probe"] = fm["probe"]
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
        out.append(entry)
    out.sort(key=lambda e: e["id"])
    return out


def collect_path_only(glob: tuple[str, ...], non_recipe_stems: frozenset[str]) -> list[str]:
    """Build a flat list of repo-root-relative paths for a category.

    Used for stack[], cross_cutting_docs[] — reference docs the consumer
    needs to know exist but they don't carry structured metadata worth
    lifting into the catalog beyond the path itself.
    """
    return sorted(
        str(p.relative_to(REPO_ROOT).as_posix())
        for p in iter_files(glob, non_recipe_stems)
    )


def collect_pattern_docs() -> list[str]:
    """Enumerate vendored blueprint cohort overviews for the catalog's
    ``pattern_docs[]``, ``primitive_docs[]``, and ``modifier_docs[]`` lists.

    Returns one flat sorted list keyed off the four cohort dirs
    (``patterns/``, ``workflows/``, ``primitives/``, ``modifiers/``); callers
    bucket the result into per-cohort fields. Used by scaffold's alias
    resolver to convert prose mentions ("ReAct", "memory", …) to a vendored
    path.

    Replaces the previous enumeration of ``docs/patterns/*.md`` (the lighter
    mirror that has been retired in favor of the vendored canonical content).
    """
    if not VENDORED_BLUEPRINTS_DIR.is_dir():
        print(
            "warning: vendored/blueprints/ not present — run `vendir sync`",
            file=sys.stderr,
        )
        return []
    out: list[str] = []
    for cohort_dir in ("patterns", "workflows", "primitives", "modifiers"):
        cohort_root = VENDORED_BLUEPRINTS_DIR / cohort_dir
        if not cohort_root.is_dir():
            continue
        for entry in sorted(cohort_root.iterdir()):
            if not entry.is_dir():
                continue
            overview = entry / "overview.md"
            if overview.is_file():
                out.append(str(overview.relative_to(REPO_ROOT).as_posix()))
    return out


def validate_recipe_references(
    recipes: list[dict[str, Any]],
    capabilities: list[dict[str, Any]],
    blueprints_catalog: dict[str, Any],
) -> None:
    """Raise SystemExit if any recipe references an id that doesn't resolve.

    Checks ``agent_pattern`` against ``catalog.patterns[].id``, each
    ``primitives[]`` / ``modifiers[]`` entry against the matching cohort, and
    each ``capabilities[]`` id against the locally-discovered capability
    files. Recipes that don't declare an additive field are skipped. Surfaces
    bad ids at generator time instead of at scaffold runtime.
    """
    cap_ids = {c["id"] for c in capabilities if "id" in c}
    cohort_ids = {
        cohort: {e["id"] for e in (blueprints_catalog.get(cohort) or []) if "id" in e}
        for cohort in ("patterns", "primitives", "modifiers")
    }
    errors: list[str] = []
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
    if errors:
        raise SystemExit("error: recipe id-resolution failed:\n  - " + "\n  - ".join(errors))


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
) -> dict[str, Any]:
    non_recipe_stems = frozenset(
        s.lower() for s in seed.get("non_recipe_stems", list(DEFAULT_NON_RECIPE_STEMS))
    )
    catalog: dict[str, Any] = OrderedDict()
    catalog["schema_version"] = SCHEMA_VERSION
    catalog["generator_version"] = GENERATOR_VERSION

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
    catalog["frameworks"] = collect_frameworks(non_recipe_stems)
    catalog["stack"] = collect_path_only(STACK_GLOB, non_recipe_stems)
    catalog["cross_cutting_docs"] = collect_path_only(CROSS_CUTTING_GLOB, non_recipe_stems)

    # Split the blueprint cohort overviews into per-cohort lists. Older
    # scaffold versions look for the flat pattern_docs[] (kept populated with
    # patterns + workflows for back-compat); newer consumers can use the more
    # granular siblings.
    all_overviews = collect_pattern_docs()
    catalog["pattern_docs"] = sorted(
        p for p in all_overviews if "/patterns/" in p or "/workflows/" in p
    )
    catalog["primitive_docs"] = sorted(p for p in all_overviews if "/primitives/" in p)
    catalog["modifier_docs"] = sorted(p for p in all_overviews if "/modifiers/" in p)

    # Validate every recipe-side id resolves before we emit. Loud failure
    # here is better than silent skip at scaffold runtime.
    validate_recipe_references(catalog["recipes"], catalog["capabilities"], blueprints_catalog)

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
    )

    body = render_yaml(catalog)
    header = (
        "# Auto-generated by scripts/generate_catalog.py — do not edit.\n"
        "# Edit source docs (their YAML frontmatter) or the upstream blueprints\n"
        "# catalog, then regenerate.\n"
    )
    Path(args.out).write_text(header + body, encoding="utf-8")

    print(
        f"Wrote {args.out} "
        f"({len(catalog['recipes'])} recipes, "
        f"{len(catalog['capabilities'])} capabilities, "
        f"{len(catalog['frameworks'])} frameworks, "
        f"{len(catalog['patterns'])} patterns + "
        f"{len(catalog['primitives'])} primitives + "
        f"{len(catalog['modifiers'])} modifiers embedded, "
        f"{len(catalog['compositions'])} compositions)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
