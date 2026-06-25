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


def test_capability_kind_must_be_in_canonical_list() -> None:
    """A capability's `kind` must be one of VALID_CAPABILITY_KINDS — the
    producer-side mirror of the scaffold's _KNOWN_KINDS."""
    bad = {
        "id": "vector_db.ghost",
        "kind": "ghost_kind",
        "path": "docs/capabilities/vector_db/ghost.md",
    }
    try:
        g.validate_recipe_references([], [bad], {}, allow_missing_required=True)
    except SystemExit as exc:
        assert "kind" in str(exc)
        assert "ghost_kind" in str(exc)
    else:
        raise AssertionError("unknown capability kind must fail validation")

    # Every canonical kind passes.
    for ok_kind in sorted(g.VALID_CAPABILITY_KINDS):
        ok = {"id": f"{ok_kind}.x", "kind": ok_kind, "path": "docs/capabilities/x.md"}
        g.validate_recipe_references([], [ok], {}, allow_missing_required=True)


def test_canonical_capability_kinds_match_schema_doc() -> None:
    """VALID_CAPABILITY_KINDS must equal SCHEMA.md's documented allowed kinds —
    the doc is the source of truth; this guards the generator (and the scaffold
    _KNOWN_KINDS mirror) against drifting."""
    import re

    schema = (g.REPO_ROOT / "docs" / "recipes" / "SCHEMA.md").read_text(encoding="utf-8")
    line = next(
        ln
        for ln in schema.splitlines()
        if "Allowed kinds:" in ln and "`vector_db`" in ln
    )
    documented = set(re.findall(r"`([a-z_]+)`", line))
    assert documented == set(g.VALID_CAPABILITY_KINDS), (
        documented ^ set(g.VALID_CAPABILITY_KINDS)
    )


def test_required_files_must_name_entry_point() -> None:
    """A recipe that lists files must include a recognized backend entry point —
    run discovers the entry by basename, so otherwise it can't launch."""
    base = {"path": "docs/recipes/r.md"}

    # Source + tests but no entry point → hard error.
    bad = dict(base)
    bad["required_files"] = ["Dockerfile", "docker-compose.yml", "tests/unit/test_x.py"]
    try:
        g.validate_recipe_references([bad], [], {}, allow_missing_required=True)
    except SystemExit as exc:
        assert "entry point" in str(exc)
    else:
        raise AssertionError("required_files without an entry point must fail")

    # With an entry point → passes.
    ok = dict(base)
    ok["required_files"] = ["Dockerfile", "app/main.py", "tests/unit/test_x.py"]
    g.validate_recipe_references([ok], [], {}, allow_missing_required=True)

    # A TypeScript entry point also satisfies the rule.
    ok_ts = dict(base)
    ok_ts["required_files"] = ["Dockerfile", "src/index.ts"]
    g.validate_recipe_references([ok_ts], [], {}, allow_missing_required=True)

    # Empty required_files is not checked by this rule.
    g.validate_recipe_references([dict(base)], [], {}, allow_missing_required=True)


def test_port_collision_across_resolved_stack() -> None:
    """No two compose services in a recipe's resolved capability stack (incl. the
    app on APP_PORT and transitive `requires`) may bind the same host port."""
    caps = [
        {"id": "cache.redis", "kind": "cache", "path": "p", "ports": ["6379:6379"]},
        {"id": "vector_db.ghost", "kind": "vector_db", "path": "p", "ports": ["6379:6379"]},
    ]
    clash = {"path": "docs/recipes/r.md", "capabilities": ["cache.redis", "vector_db.ghost"]}
    try:
        g.validate_recipe_references([clash], caps, {}, allow_missing_required=True)
    except SystemExit as exc:
        assert "host port 6379" in str(exc)
    else:
        raise AssertionError("two services on the same host port must fail")

    # Distinct host ports → passes.
    caps_ok = [
        {"id": "cache.redis", "kind": "cache", "path": "p", "ports": ["6379:6379"]},
        {"id": "vector_db.ok", "kind": "vector_db", "path": "p", "ports": ["6333:6333"]},
    ]
    ok = {"path": "docs/recipes/r.md", "capabilities": ["cache.redis", "vector_db.ok"]}
    g.validate_recipe_references([ok], caps_ok, {}, allow_missing_required=True)

    # A capability colliding with the app's default 8000 → fails.
    app_clash_caps = [
        {"id": "frontend.x", "kind": "frontend", "path": "p", "ports": ["8000:8000"]}
    ]
    app_clash = {"path": "docs/recipes/r.md", "capabilities": ["frontend.x"]}
    try:
        g.validate_recipe_references([app_clash], app_clash_caps, {}, allow_missing_required=True)
    except SystemExit as exc:
        assert "8000" in str(exc)
    else:
        raise AssertionError("a capability colliding with the app port must fail")

    # A transitive `requires` dependency's port also participates.
    transitive_caps = [
        {"id": "obs.x", "kind": "obs", "path": "p", "ports": ["5432:5432"], "requires": ["relational.y"]},
        {"id": "relational.y", "kind": "relational", "path": "p", "ports": ["5432:5432"]},
    ]
    transitive = {"path": "docs/recipes/r.md", "capabilities": ["obs.x"]}
    try:
        g.validate_recipe_references([transitive], transitive_caps, {}, allow_missing_required=True)
    except SystemExit as exc:
        assert "host port 5432" in str(exc)
    else:
        raise AssertionError("a transitive requires port collision must fail")


def test_load_list_path_must_resolve_on_disk() -> None:
    """Every load_list[].path must resolve to a file on disk — the producer
    fails closed (the consumer fails open with a warning)."""
    # A dead link in a real recipe dir → hard error.
    bad = {
        "path": "docs/recipes/docs-rag-qa.md",
        "load_list": [{"path": "../does-not-exist/ghost.md", "required": True}],
    }
    try:
        g.validate_recipe_references([bad], [], {}, allow_missing_required=True)
    except SystemExit as exc:
        assert "does not resolve" in str(exc)
    else:
        raise AssertionError("a dead load_list link must fail")

    # A resolvable link → passes (project-layout.md exists in this repo).
    ok = {
        "path": "docs/recipes/docs-rag-qa.md",
        "load_list": [{"path": "../cross-cutting/project-layout.md", "required": True}],
    }
    g.validate_recipe_references([ok], [], {}, allow_missing_required=True)


def test_advertisement_coherence_warns_on_unbacked_provider() -> None:
    """A provider named in a runtime_modes description but backed by neither a
    capability nor a dependency is an advisory warning (never a build failure)."""
    unbacked = {
        "path": "docs/recipes/r.md",
        "runtime_modes": {"default": {"description": "Claude + Zep for memory."}},
        "capabilities": ["cache.redis"],
        "recipe_dependencies": {"python": {"redis": ">=5"}},
    }
    warnings = g.report_content_warnings([unbacked], [], [], {})
    assert any("zep" in w and "r.md" in w for w in warnings), warnings

    # Backed by a capability → no advertisement warning for that provider.
    backed = {
        "path": "docs/recipes/ok.md",
        "runtime_modes": {"default": {"description": "Claude + Qdrant retrieval."}},
        "capabilities": ["vector_db.qdrant"],
        "recipe_dependencies": {"python": {"qdrant-client": ">=1"}},
    }
    warnings = g.report_content_warnings([backed], [], [], {})
    assert not any("qdrant" in w for w in warnings), warnings


def test_orphan_pattern_is_advisory_warning() -> None:
    """A blueprint pattern that no recipe selects is flagged as a coverage-gap
    warning, not a hard error."""
    blueprints = {"patterns": [{"id": "rag"}, {"id": "saga"}]}
    recipes = [{"path": "docs/recipes/r.md", "agent_pattern": "rag"}]
    warnings = g.report_content_warnings(recipes, [], [], blueprints)
    assert any("saga" in w for w in warnings), warnings
    assert not any("'rag'" in w and "no recipe" in w for w in warnings), warnings


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"ok: {test.__name__}")
    print(f"{len(tests)} catalog-validation self-tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
