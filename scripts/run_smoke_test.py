#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["PyYAML>=6.0"]
# ///
"""Run a recipe's smoke_test end-to-end and report pass/fail.

Invoked by ``.github/workflows/recipe-smoke.yml`` for each validated recipe
on workflow_dispatch (and on the daily cron when secrets land).

What it does:

  1. Parse ``catalog.yaml`` and locate ``recipes[<slug>]``.
  2. If the recipe has a ``## Reference Implementation`` body, that's the
     project to bring up. Otherwise the recipe is design-spec only — the
     script exits 2 (skipped, not failed) and the workflow surfaces it.
  3. Walk the recipe's ``load_list[]`` and copy only the ``required: true``
     ``cache_tier: hot`` entries into the working directory. Saves context
     budget on any downstream LLM-driven validation (April 2026 GitHub Blog
     guidance: matrix workflows save 8-12 KB per call by pruning unused
     content).
  4. ``docker compose up -d`` for the recipe's services, run the recipe's
     ``bootstrap_step``s in ``LAYER_ORDER``.
  5. Loop on ``smoke_test.ready`` until exit 0 (5 min timeout).
  6. Run ``smoke_test.exercise`` and capture stdout.
  7. Evaluate ``smoke_test.assert_jq`` against stdout.
  8. Optionally evaluate every ``acceptance_contracts.smoke_assertions[].jq``.
  9. Exit 0 on success, 1 on failure, 2 on skip.

This is a skeleton — the reference-implementation discovery step (#2) and the
actual bootstrap walk (#4) are punted until per-recipe reference projects
land. For now the script validates the catalog wiring (steps 1, 3, 9) and
prints what it WOULD execute so the workflow can dry-run.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG = REPO_ROOT / "catalog.yaml"


def load_recipe(slug: str) -> dict:
    catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    recipe = next((r for r in catalog["recipes"] if r["slug"] == slug), None)
    if recipe is None:
        sys.exit(f"error: recipe {slug!r} not found in catalog.yaml")
    return recipe


def has_reference_implementation(recipe: dict) -> bool:
    body = (REPO_ROOT / recipe["path"]).read_text(encoding="utf-8")
    # A validated recipe has a non-pseudocode ## Reference Implementation
    # heading. Design-spec recipes either omit the section or label it
    # "## Reference Implementation (pseudocode)".
    for line in body.splitlines():
        stripped = line.strip()
        if stripped == "## Reference Implementation":
            return True
        if stripped.startswith("## Reference Implementation (pseudocode)"):
            return False
    return False


def collect_hot_load_list(recipe: dict) -> list[str]:
    """Return the repo-relative paths the consumer should mount.

    The cost-saving heuristic from the workflow's cost note: keep only
    required + cache_tier: hot entries; the rest can be lazy-fetched.
    """
    out: list[str] = []
    recipe_dir = (REPO_ROOT / recipe["path"]).parent
    for entry in recipe.get("load_list") or []:
        if not isinstance(entry, dict):
            continue
        if not entry.get("required", True):
            continue
        if entry.get("cache_tier") != "hot":
            continue
        resolved = (recipe_dir / entry["path"]).resolve()
        try:
            out.append(str(resolved.relative_to(REPO_ROOT)))
        except ValueError:
            # outside repo; skip silently
            continue
    return out


def wait_ready(cmd: str, timeout_s: int = 300) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        result = subprocess.run(cmd, shell=True, capture_output=True)
        if result.returncode == 0:
            return True
        time.sleep(2)
    return False


def run_exercise(cmd: str) -> tuple[bool, str]:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0, result.stdout


def jq_truthy(stdout: str, expression: str) -> bool:
    try:
        result = subprocess.run(
            ["jq", "-e", expression],
            input=stdout,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        sys.exit("error: jq is not installed on this runner")
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("recipe", help="recipe slug to smoke (e.g. research-assistant)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be executed and exit 0. Useful while reference implementations land.",
    )
    args = parser.parse_args()

    recipe = load_recipe(args.recipe)
    print(f"[smoke] recipe: {recipe['slug']} — {recipe.get('title')}")
    print(f"[smoke] runtime_modes: {sorted((recipe.get('runtime_modes') or {}).keys())}")

    hot = collect_hot_load_list(recipe)
    print(f"[smoke] hot load_list entries: {len(hot)}")
    for p in hot:
        print(f"          - {p}")

    if not has_reference_implementation(recipe):
        print(f"[smoke] {recipe['slug']} has no ## Reference Implementation; skipping live bring-up.")
        return 2

    smoke = recipe.get("smoke_test") or {}
    if not all(smoke.get(k) for k in ("ready", "exercise", "assert_jq")):
        sys.exit("error: smoke_test must have ready / exercise / assert_jq")

    if args.dry_run:
        print("[smoke] DRY-RUN — would execute:")
        print(f"  ready:    {smoke['ready']}")
        print(f"  exercise: {smoke['exercise']}")
        print(f"  assert:   {smoke['assert_jq']}")
        return 0

    print(f"[smoke] waiting for ready: {smoke['ready']}")
    if not wait_ready(smoke["ready"]):
        print("[smoke] FAIL: ready probe never succeeded within 5min")
        return 1

    print(f"[smoke] running exercise")
    ok, stdout = run_exercise(smoke["exercise"])
    if not ok:
        print(f"[smoke] FAIL: exercise exited non-zero. stdout: {stdout[:500]}")
        return 1

    print(f"[smoke] evaluating assert_jq: {smoke['assert_jq']}")
    if not jq_truthy(stdout, smoke["assert_jq"]):
        print(f"[smoke] FAIL: assert_jq was not truthy. stdout: {stdout[:500]}")
        return 1
    print("[smoke] assert_jq: pass")

    # Optional: walk acceptance_contracts.smoke_assertions[]
    ac = recipe.get("acceptance_contracts") or {}
    for i, sa in enumerate(ac.get("smoke_assertions") or []):
        expr = sa.get("jq")
        if not expr:
            continue
        if not jq_truthy(stdout, expr):
            print(f"[smoke] FAIL: acceptance_contracts.smoke_assertions[{i}] was not truthy")
            return 1
        print(f"[smoke] acceptance_contracts.smoke_assertions[{i}]: pass")

    print(f"[smoke] {recipe['slug']}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
