#!/usr/bin/env python3
"""Self-tests for generate_catalog.py's validation rules.

Stdlib-only (no pytest) so CI and contributors can run it directly:

    python scripts/test_catalog_validation.py

Covers the producer-side contract checks that protect consumers:
- load_list[].when predicate grammar (fail-closed here; consumers fail open)
- acceptance_contracts presence rules for validated vs design-spec recipes
- required_env ↔ derived env_contract cross-check
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_catalog as g  # noqa: E402


def _predicate_errors(predicate: object, cap_ids: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    g._validate_load_list_predicate(predicate, "test", cap_ids or set(), errors)
    return errors


def test_predicate_grammar_accepts_both_forms() -> None:
    for ok in (
        "language == 'python'",
        'language == "python"',
        "framework == 'pydantic_ai'",
        "topology == 'single'",
        "  topology  ==  'multi-agent-flat'  ",
        "capabilities contains 'obs.langfuse'",
        'capabilities contains "cache.redis"',
        None,  # absent predicate is always fine
    ):
        cap_ids = {"obs.langfuse", "cache.redis"}
        assert _predicate_errors(ok, cap_ids) == [], f"falsely rejected: {ok!r}"


def test_predicate_grammar_rejects_everything_else() -> None:
    for bad in (
        "language != 'python'",  # only == exists
        "model == 'opus'",  # unknown attribute
        "language == python",  # unquoted value
        "language == 'python' and topology == 'single'",  # no conjunctions
        "capabilities contains obs.langfuse",  # unquoted id
        "not capabilities contains 'x'",  # no negation
        "",  # empty string (allowed only as absent/None)
        123,  # non-string
    ):
        assert _predicate_errors(bad), f"falsely accepted: {bad!r}"


def test_predicate_contains_id_must_resolve() -> None:
    errors = _predicate_errors("capabilities contains 'ghost.capability'", {"cache.redis"})
    assert errors and "ghost.capability" in errors[0]


def test_required_env_cross_check() -> None:
    recipes = [
        {
            "path": "docs/recipes/x.md",
            "acceptance_contracts": {
                "required_env": [
                    # In the derived contract → fine.
                    {"name": "REDIS_URL", "source": "capability:cache.redis"},
                    # Capability-sourced but never declared → must fail.
                    {"name": "GHOST_VAR", "source": "capability:cache.redis"},
                    # Prompted sources are recipe-specific → exempt.
                    {"name": "USER_TOKEN", "source": "prompted"},
                ]
            },
            "env_contract": [{"name": "REDIS_URL", "source_capability": "cache.redis"}],
        }
    ]
    try:
        g.validate_required_env_against_contract(recipes)
    except SystemExit as exc:
        message = str(exc)
        assert "GHOST_VAR" in message
        assert "USER_TOKEN" not in message
        assert "REDIS_URL" not in message.replace("GHOST_VAR", "")
    else:
        raise AssertionError("expected SystemExit for GHOST_VAR")


def test_required_env_cross_check_passes_clean_recipe() -> None:
    g.validate_required_env_against_contract(
        [
            {
                "path": "docs/recipes/ok.md",
                "acceptance_contracts": {
                    "required_env": [{"name": "REDIS_URL", "source": "capability:cache.redis"}]
                },
                "env_contract": [{"name": "redis_url", "source_capability": "cache.redis"}],
            }
        ]
    )  # case-insensitive match; must not raise


def test_validated_recipe_requires_all_acceptance_blocks() -> None:
    """Exercise the recipe-loop rule through validate_recipe_references."""
    base = {
        "path": "docs/recipes/v.md",
        "status": "Blueprint (validated)",
        "runtime_modes": {"default": {"swaps": {}}},
        "smoke_test": {"ready": "r", "exercise": "e", "assert_jq": "j"},
        "cost_profile": {"tier": "low", "sources": []},
    }
    # Missing block entirely → hard error.
    try:
        g.validate_recipe_references([dict(base)], [], {}, allow_missing_required=True)
    except SystemExit as exc:
        assert "acceptance_contracts" in str(exc)
    else:
        raise AssertionError("validated recipe without acceptance_contracts must fail")

    # All four keys present (even empty) → passes.
    ok = dict(base)
    ok["acceptance_contracts"] = {
        "http_endpoints": [{"path": "/health"}],
        "required_env": [],
        "required_compose_services": [],
        "smoke_assertions": [],
    }
    g.validate_recipe_references([ok], [], {}, allow_missing_required=True)

    # One key absent → hard error naming it.
    partial = dict(base)
    partial["acceptance_contracts"] = {
        "http_endpoints": [{"path": "/health"}],
        "required_env": [],
        "required_compose_services": [],
    }
    try:
        g.validate_recipe_references([partial], [], {}, allow_missing_required=True)
    except SystemExit as exc:
        assert "smoke_assertions" in str(exc)
    else:
        raise AssertionError("missing smoke_assertions must fail on validated recipes")


def test_topology_must_be_in_canonical_list() -> None:
    """A recipe's `topology` must be one of SCHEMA.md's canonical values — the
    producer-side mirror of the scaffold's Topology enum."""
    base = {"path": "docs/recipes/t.md"}

    # Out-of-list topology → hard error naming the offending value.
    bad = dict(base)
    bad["topology"] = "swarm"  # never canonical; dropped from the list
    try:
        g.validate_recipe_references([bad], [], {}, allow_missing_required=True)
    except SystemExit as exc:
        assert "topology" in str(exc)
        assert "swarm" in str(exc)
    else:
        raise AssertionError("out-of-list topology must fail validation")

    # Every canonical value passes (no topology error raised).
    for ok_topology in sorted(g.VALID_TOPOLOGIES):
        ok = dict(base)
        ok["topology"] = ok_topology
        g.validate_recipe_references([ok], [], {}, allow_missing_required=True)

    # Absent topology is allowed — the consumer infers a default.
    g.validate_recipe_references([dict(base)], [], {}, allow_missing_required=True)


def test_canonical_topologies_match_schema_doc() -> None:
    """VALID_TOPOLOGIES must equal SCHEMA.md's documented allowed values — the
    doc is the source of truth; this guards the generator against drifting."""
    import re

    schema = (g.REPO_ROOT / "docs" / "recipes" / "SCHEMA.md").read_text(encoding="utf-8")
    # The `#### topology` section's "Allowed values:" line lists `value` codes.
    line = next(
        ln for ln in schema.splitlines() if "Allowed values:" in ln and "`single`" in ln
    )
    documented = set(re.findall(r"`([a-z-]+)`", line))
    assert documented == set(g.VALID_TOPOLOGIES), (documented, set(g.VALID_TOPOLOGIES))


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"ok: {test.__name__}")
    print(f"{len(tests)} catalog-validation self-tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
