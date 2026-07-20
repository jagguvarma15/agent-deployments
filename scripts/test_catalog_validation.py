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


def test_t0_core_capabilities_present() -> None:
    """The T0 chat substrate (core.prompts, core.io_schema) is in the catalog as
    `core` capabilities, so the T0 tier's seeds resolve instead of going inert."""
    caps = {c["id"]: c for c in g.collect_capabilities(frozenset(g.DEFAULT_NON_RECIPE_STEMS))}
    for cid in ("core.prompts", "core.io_schema"):
        assert cid in caps, f"{cid} missing from collected capabilities"
        assert caps[cid]["kind"] == "core"


def test_t0_core_capability_templates_exist() -> None:
    """Each T0 core capability ships the template files its emit_files declares —
    the scaffold copies these verbatim into the generated project."""
    base = g.REPO_ROOT / "docs" / "capabilities" / "core" / "templates"
    for rel in (
        "prompts/loader.py",
        "prompts/__init__.py",
        "prompts/system.txt",
        "prompts/README.md",
        "io_schema/schemas.py",
        "io_schema/__init__.py",
        "io_schema/README.md",
    ):
        assert (base / rel).is_file(), f"missing template {rel}"


def test_t0_prompt_templates_have_no_stray_markdown() -> None:
    """Prompt templates are .txt (not .md): the scaffold's capability loader
    recurses `docs/capabilities/**/*.md`, so a non-README .md under templates
    would trip a spurious 'missing frontmatter' warning on every run."""
    prompts = g.REPO_ROOT / "docs" / "capabilities" / "core" / "templates" / "prompts"
    stray = [p.name for p in prompts.glob("*.md") if p.stem.lower() != "readme"]
    assert not stray, f"non-README .md prompt templates would warn on load: {stray}"


def test_t2_core_step_log_present() -> None:
    """The T2 workflow substrate (core.step_log) is in the catalog as a `core`
    capability, so the T2 tier's seed resolves instead of going inert."""
    caps = {c["id"]: c for c in g.collect_capabilities(frozenset(g.DEFAULT_NON_RECIPE_STEMS))}
    assert "core.step_log" in caps, "core.step_log missing from collected capabilities"
    assert caps["core.step_log"]["kind"] == "core"


def test_t2_core_step_log_template_exists() -> None:
    """core.step_log ships the single module its emit_files declares — the
    scaffold copies it verbatim to agent/steplog.py in the generated project."""
    template = (
        g.REPO_ROOT / "docs" / "capabilities" / "core" / "templates" / "step_log" / "steplog.py"
    )
    assert template.is_file(), "missing template step_log/steplog.py"


def test_tier_presets_are_structurally_valid() -> None:
    """The published T0→T4 ladder passes structural validation and carries the
    expected tier names."""
    tiers = g.build_tiers()
    g.validate_tiers(tiers)  # must not raise
    assert [t["name"] for t in tiers] == ["T0", "T1", "T2", "T3", "T4"]


def test_tiers_form_superset_chain() -> None:
    """Each tier extends the one below (T4 ⊇ … ⊇ T0), so the scaffold expands a
    tier into a strict superset of every tier under it."""
    by_name = {t["name"]: t for t in g.build_tiers()}
    assert by_name["T0"]["extends"] is None
    for lower, higher in (("T0", "T1"), ("T1", "T2"), ("T2", "T3"), ("T3", "T4")):
        assert by_name[higher]["extends"] == lower


def test_tier_ladder_carries_expected_capabilities() -> None:
    """Content lock: the core primitives each tier introduces stay put, so the
    ladder can't silently lose a capability across a regen."""
    by_name = {t["name"]: t for t in g.build_tiers()}
    assert "core.spec" in by_name["T0"]["capabilities"]
    assert "core.tool_registry" in by_name["T1"]["capabilities"]
    assert "core.step_log" in by_name["T2"]["capabilities"]
    assert "eval.promptfoo" in by_name["T3"]["capabilities"]
    assert "human_in_the_loop" in by_name["T4"]["overlays"]


def test_validate_tiers_rejects_unknown_extends() -> None:
    tiers = [{"name": "T0", "extends": None}, {"name": "T1", "extends": "T9"}]
    try:
        g.validate_tiers(tiers)
    except SystemExit as exc:
        assert "T9" in str(exc)
    else:
        raise AssertionError("extends of an unknown tier must fail validation")


def test_validate_tiers_rejects_cycle() -> None:
    tiers = [{"name": "A", "extends": "B"}, {"name": "B", "extends": "A"}]
    try:
        g.validate_tiers(tiers)
    except SystemExit as exc:
        assert "cycle" in str(exc)
    else:
        raise AssertionError("a cycle in the extends chain must fail validation")


def test_validate_tiers_rejects_duplicate_name() -> None:
    tiers = [{"name": "T0", "extends": None}, {"name": "T0", "extends": None}]
    try:
        g.validate_tiers(tiers)
    except SystemExit as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("a duplicate tier name must fail validation")


def test_bundle_presets_are_structurally_valid() -> None:
    """The published bundles pass validation against the real capability set
    and keep their names — the scaffold's preset pickers key on these."""
    bundles = g.build_bundles()
    caps = g.collect_capabilities(frozenset(g.DEFAULT_NON_RECIPE_STEMS))
    g.validate_bundles(bundles, caps)  # must not raise
    assert [b["name"] for b in bundles] == [
        "rag-simple",
        "rag-complex",
        "rag-local",
        "guardrails-basic",
    ]


def test_bundles_expand_to_expected_capabilities() -> None:
    """Content lock: the preset shapes stay put across regens."""
    by_name = {b["name"]: b for b in g.build_bundles()}
    assert by_name["rag-simple"]["capabilities"] == ["vector_db.pgvector", "embedding.openai"]
    assert by_name["rag-complex"]["capabilities"] == [
        "vector_db.qdrant",
        "embedding.openai",
        "rerank.cohere",
    ]
    assert by_name["rag-local"]["capabilities"] == ["vector_db.pgvector", "embedding.local-bge"]
    assert by_name["guardrails-basic"]["capabilities"] == ["guardrail.llama-guard"]


def test_validate_bundles_rejects_unknown_capability() -> None:
    """Unlike tiers, bundle ids must resolve — a preset that expands to a
    missing id silently drops a layer from the generated stack."""
    bundles = [{"name": "x", "title": "X", "description": "d", "capabilities": ["vector_db.nope"]}]
    caps = [{"id": "vector_db.pgvector"}]
    try:
        g.validate_bundles(bundles, caps)
    except SystemExit as exc:
        assert "vector_db.nope" in str(exc)
    else:
        raise AssertionError("an unknown bundle capability id must fail validation")


def test_validate_bundles_rejects_duplicate_and_empty() -> None:
    caps = [{"id": "cache.redis"}]
    bundles = [
        {"name": "dup", "title": "A", "description": "d", "capabilities": ["cache.redis"]},
        {"name": "dup", "title": "B", "description": "d", "capabilities": []},
    ]
    try:
        g.validate_bundles(bundles, caps)
    except SystemExit as exc:
        assert "duplicate" in str(exc)
        assert "no capabilities" in str(exc)
    else:
        raise AssertionError("duplicate names and empty bundles must fail validation")


def test_obs_hosting_flows_from_frontmatter() -> None:
    """The authored hosting modes surface on the generated entries; the field
    stays opt-in for capabilities that never author it."""
    caps = {c["id"]: c for c in g.collect_capabilities(frozenset(g.DEFAULT_NON_RECIPE_STEMS))}
    assert caps["obs.langfuse"]["hosting"] == ["cloud", "docker"]
    assert caps["obs.langsmith"]["hosting"] == ["cloud"]
    assert caps["obs.grafana-stack"]["hosting"] == ["docker"]
    assert "hosting" not in caps["cache.redis"]


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

    # A blueprint GitHub URL → exempt from the on-disk check (no vendoring; the
    # consumer resolves it against its own blueprints checkout).
    bp = {
        "path": "docs/recipes/docs-rag-qa.md",
        "load_list": [
            {
                "path": "https://github.com/jagguvarma15/agent-blueprints/blob/main/patterns/react/overview.md",
                "required": True,
            }
        ],
    }
    g.validate_recipe_references([bp], [], {}, allow_missing_required=True)


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


# Vendored copies of the producer's lint constants, pinned here so a one-sided
# edit to generate_catalog.py fails CI. The cross-repo tie is: this copy + the
# scaffold-side parity test (tests/test_content_lint.py) both pin their repo's
# constant to the same literal. When a constant changes, update BOTH repos'
# constants AND both vendored copies.
CANONICAL_ENTRY_POINT_BASENAMES = frozenset(
    {
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
    }
)
CANONICAL_ADVERTISED_PROVIDERS = {
    "qdrant": ("qdrant", "qdrant"),
    "chroma": ("chroma", "chroma"),
    "pgvector": ("pgvector", "pgvector"),
    "openai": ("embedding.openai", "openai"),
    "cohere": ("rerank.cohere", "cohere"),
    "zep": ("memory_store.zep", "zep"),
}


def test_lint_constants_match_canonical() -> None:
    """Pin ENTRY_POINT_BASENAMES + ADVERTISED_PROVIDERS to the vendored literals
    so they can't drift from the scaffold's content_lint mirror unnoticed."""
    assert g.ENTRY_POINT_BASENAMES == CANONICAL_ENTRY_POINT_BASENAMES
    assert g.ADVERTISED_PROVIDERS == CANONICAL_ADVERTISED_PROVIDERS


def test_capability_kinds_documented_in_all_docs() -> None:
    """Every canonical kind must appear (backticked) in each doc that lists the
    kinds — SCHEMA.md is machine-pinned by the line test above; this also guards
    capabilities/README.md and MANIFEST_SCHEMA.md against silent drift."""
    for doc in ("docs/capabilities/README.md", "MANIFEST_SCHEMA.md"):
        text = (g.REPO_ROOT / doc).read_text(encoding="utf-8")
        missing = [k for k in g.VALID_CAPABILITY_KINDS if f"`{k}`" not in text]
        assert not missing, f"{doc} is missing kinds: {missing}"


def test_capability_card_rules() -> None:
    """Empty card.name/description is a hard error; a missing card entirely is a
    soft (migration) error — downgraded under allow_missing_required."""
    bad = {"id": "obs.x", "kind": "obs", "path": "docs/capabilities/obs/x.md",
           "card": {"name": "", "description": "d"}}
    try:
        g.validate_recipe_references([], [bad], {}, allow_missing_required=True)
    except SystemExit as exc:
        assert "card.name" in str(exc)
    else:
        raise AssertionError("empty card.name must be a hard error")

    # Missing card entirely is soft → no raise under allow_missing_required.
    nocard = {"id": "obs.y", "kind": "obs", "path": "docs/capabilities/obs/y.md"}
    g.validate_recipe_references([], [nocard], {}, allow_missing_required=True)

    # ...but hard when required fields are enforced.
    try:
        g.validate_recipe_references([], [dict(nocard)], {}, allow_missing_required=False)
    except SystemExit as exc:
        assert "card" in str(exc)
    else:
        raise AssertionError("missing card must fail when required fields are enforced")


def test_advertisement_backed_by_either_source() -> None:
    """A provider backed by a capability ALONE or a dependency ALONE is clean —
    the check warns only when BOTH are absent (OR semantics)."""
    cap_only = {
        "path": "docs/recipes/c.md",
        "runtime_modes": {"default": {"description": "Claude + Qdrant retrieval."}},
        "capabilities": ["vector_db.qdrant"],
        "recipe_dependencies": {"python": {"fastapi": ">=0"}},
    }
    assert not any("qdrant" in w for w in g.report_content_warnings([cap_only], [], [], {}))

    dep_only = {
        "path": "docs/recipes/d.md",
        "runtime_modes": {"default": {"description": "Claude + Qdrant retrieval."}},
        "capabilities": ["cache.redis"],
        "recipe_dependencies": {"python": {"qdrant-client": ">=1"}},
    }
    assert not any("qdrant" in w for w in g.report_content_warnings([dep_only], [], [], {}))


def test_orphan_framework_warns() -> None:
    """A framework doc no recipe references in its load_list is an advisory
    orphan warning; a referenced framework is clean."""
    frameworks = [{"path": "docs/frameworks/foo.md", "id": "foo"}]
    warnings = g.report_content_warnings([], [], frameworks, {})
    assert any("foo" in w and "framework" in w for w in warnings), warnings

    user = {"path": "docs/recipes/r.md", "load_list": [{"path": "../frameworks/foo.md"}]}
    warnings = g.report_content_warnings([user], [], frameworks, {})
    assert not any("framework 'foo'" in w for w in warnings), warnings


def test_check_flag_freshness() -> None:
    """--check returns 0 when catalog.yaml is a fresh regeneration, 1 when stale
    or absent, and never writes the file."""
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "catalog.yaml")
        assert g.main(["--out", out]) == 0  # write a fresh catalog
        assert g.main(["--check", "--out", out]) == 0  # fresh → ok
        with open(out, "a", encoding="utf-8") as f:
            f.write("\n# injected drift\n")
        assert g.main(["--check", "--out", out]) == 1  # stale → fail
        # --check must not have rewritten the file.
        assert Path(out).read_text(encoding="utf-8").endswith("# injected drift\n")
        os.remove(out)
        assert g.main(["--check", "--out", out]) == 1  # absent → fail
        assert not Path(out).exists()


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"ok: {test.__name__}")
    print(f"{len(tests)} catalog-validation self-tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
