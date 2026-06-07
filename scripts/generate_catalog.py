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
   ``docs/frameworks/*.md``, ``docs/stack/*.md``, ``docs/cross-cutting/*.md``,
   ``docs/patterns/*.md``. Parses each file's YAML frontmatter via PyYAML.
2. Fetches ``patterns-catalog.yaml`` from the agent-blueprints repo (default
   URL: raw.githubusercontent.com main branch; overridable via
   ``--blueprints-catalog-url``). Extracts its ``patterns[]``, ``workflows[]``,
   and ``compositions[]`` blocks and embeds them.
3. Queries the GitHub Commits API for the blueprints HEAD SHA and stamps it
   as ``blueprints.upstream_sha``. This pins which blueprints revision the
   deployments catalog was built against, so consumers can detect upstream
   drift even when the deployments catalog hasn't been regenerated.
4. Reads ``scripts/_seed_aliases.yaml`` for the v1 alias / cross-cutting /
   non-recipe-stems / min-alias-length blocks. (v1.1 will move alias data
   into per-doc frontmatter.)
5. Emits ``catalog.yaml`` (or ``--out <path>``) via deterministic PyYAML dump
   (sort_keys=False, no flow style, no timestamps).

Determinism notes:

- No ``generated_at``, no source-side ``source_commit_sha`` — both would
  break the drift check's byte-diff. The blueprints upstream SHA is the
  only externally-derived field, and it's stable per upstream commit.
- All collections are sorted before emit: recipes / capabilities / frameworks
  / stack / cross-cutting / patterns by their natural primary key.
- Aliases and cross-cutting maps inherit the seed file's insertion order
  (which is the legacy ALIAS_TABLE order from scaffold).

Local development:

    # Run against PR #43's branch URL while it's still unmerged:
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
import json
import re
import sys
import urllib.error
import urllib.request
from collections import OrderedDict
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = 1
GENERATOR_VERSION = "1.0.0"

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = REPO_ROOT / "docs"

DEFAULT_BLUEPRINTS_CATALOG_URL = (
    "https://raw.githubusercontent.com/jagguvarma15/agent-blueprints/main/patterns-catalog.yaml"
)
DEFAULT_BLUEPRINTS_REPO = "jagguvarma15/agent-blueprints"
DEFAULT_BLUEPRINTS_BRANCH = "main"

NETWORK_TIMEOUT_SECONDS = 10.0

# Source files for each section. Globs are relative to DOCS_ROOT.
RECIPE_GLOB = ("recipes", "*.md")
CAPABILITY_GLOB = ("capabilities", "*", "*.md")
FRAMEWORK_GLOB = ("frameworks", "*.md")
STACK_GLOB = ("stack", "*.md")
CROSS_CUTTING_GLOB = ("cross-cutting", "*.md")
PATTERN_GLOB = ("patterns", "*.md")

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

    Used for stack[], cross_cutting_docs[], patterns[] — these are reference
    docs the consumer needs to know exist but they don't carry structured
    metadata worth lifting into the catalog beyond the path itself.
    """
    return sorted(
        str(p.relative_to(REPO_ROOT).as_posix())
        for p in iter_files(glob, non_recipe_stems)
    )


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


def fetch_blueprints_head_sha(repo: str, branch: str) -> str | None:
    """Return the HEAD commit SHA on ``branch`` of ``repo``, or None on failure.

    Uses the public GitHub Commits API. Anonymous; subject to the unauth
    rate limit (60 req/hr/IP). Failures (offline, rate-limited, 404) return
    None — the generator stamps ``upstream_sha: null`` and continues so a
    local dev run without network still produces a usable catalog.
    """
    url = f"https://api.github.com/repos/{repo}/commits/{branch}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            sha = payload.get("sha")
            return sha if isinstance(sha, str) else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        print(
            f"warning: could not fetch blueprints HEAD SHA from {url}: {exc}",
            file=sys.stderr,
        )
        return None


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
    blueprints_url: str,
    blueprints_repo: str,
    blueprints_branch: str,
    blueprints_upstream_sha: str | None,
) -> dict[str, Any]:
    non_recipe_stems = frozenset(
        s.lower() for s in seed.get("non_recipe_stems", list(DEFAULT_NON_RECIPE_STEMS))
    )
    catalog: dict[str, Any] = OrderedDict()
    catalog["schema_version"] = SCHEMA_VERSION
    catalog["generator_version"] = GENERATOR_VERSION

    # Blueprints pointer block — the dependency declaration this repo makes
    # explicit so downstream consumers (scaffold) never reach into blueprints
    # by name.
    blueprints_block: dict[str, Any] = OrderedDict()
    blueprints_block["repo"] = blueprints_repo
    blueprints_block["branch"] = blueprints_branch
    blueprints_block["catalog_url"] = blueprints_url
    blueprints_block["catalog_path"] = "patterns-catalog.yaml"
    blueprints_block["upstream_sha"] = blueprints_upstream_sha
    # URL pattern + directory entry: scaffold uses these to resolve recipe-body
    # links of the form `github.com/.../agent-blueprints/...` to local paths
    # in the fetched blueprints tree, without hardcoding the convention itself.
    blueprints_block["url_pattern"] = "https://github.com/{repo}/(?:tree|blob|raw)/{branch}/{path}"
    blueprints_block["directory_entry"] = "overview.md"
    catalog["blueprints"] = blueprints_block

    # Embedded blueprints index. Pass-through; we don't restructure.
    catalog["patterns"] = blueprints_catalog.get("patterns") or []
    catalog["workflows"] = blueprints_catalog.get("workflows") or []
    catalog["compositions"] = blueprints_catalog.get("compositions") or []

    # This repo's own content.
    catalog["recipes"] = collect_recipes(non_recipe_stems)
    catalog["capabilities"] = collect_capabilities(non_recipe_stems)
    catalog["frameworks"] = collect_frameworks(non_recipe_stems)
    catalog["stack"] = collect_path_only(STACK_GLOB, non_recipe_stems)
    catalog["cross_cutting_docs"] = collect_path_only(CROSS_CUTTING_GLOB, non_recipe_stems)
    catalog["pattern_docs"] = collect_path_only(PATTERN_GLOB, non_recipe_stems)

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
        "--skip-sha-fetch",
        action="store_true",
        help="Skip the GitHub Commits API call for the blueprints upstream SHA. "
        "Useful for offline runs or when iterating on a non-default branch. "
        "Sets upstream_sha to null in the output.",
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

    if args.skip_sha_fetch:
        upstream_sha = None
    else:
        upstream_sha = fetch_blueprints_head_sha(args.blueprints_repo, args.blueprints_branch)

    catalog = build_catalog(
        seed=seed,
        blueprints_catalog=blueprints_catalog,
        blueprints_url=args.blueprints_catalog_url,
        blueprints_repo=args.blueprints_repo,
        blueprints_branch=args.blueprints_branch,
        blueprints_upstream_sha=upstream_sha,
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
        f"{len(catalog['patterns'])} patterns embedded, "
        f"{len(catalog['workflows'])} workflows embedded, "
        f"{len(catalog['compositions'])} compositions embedded)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
