"""End-to-end walkthrough tests for the release-checklist overlay.

Runs offline — planner, executor, replanner are deterministic stubs in
``main``. Real production swaps each for an ``anthropic`` Agent call.

Run:
    uv run --with pydantic --with pytest python -m pytest test_walkthrough.py -v

Or as a script:
    uv run --with pydantic python test_walkthrough.py
"""

from __future__ import annotations

from .main import run_release
from .schemas import ReleaseEnv, ReleaseStepKind


def test_happy_path_release_succeeds_without_replan() -> None:
    report = run_release("1.4.2", ReleaseEnv.staging)
    assert report.status == "succeeded"
    assert report.replanned is False
    # Four steps: build -> smoke -> deploy -> verify, each on `web`.
    kinds = [r.kind for r in report.results]
    assert kinds == [
        ReleaseStepKind.build,
        ReleaseStepKind.smoke,
        ReleaseStepKind.deploy,
        ReleaseStepKind.verify,
    ]
    assert all(r.success for r in report.results)


def test_smoke_failure_triggers_fix_step_then_succeeds() -> None:
    report = run_release("1.4.3", ReleaseEnv.staging)
    assert report.status == "succeeded"
    assert report.replanned is True
    kinds = [r.kind for r in report.results]
    # Expected sequence: build -> smoke(fail) -> fix -> smoke(ok) -> deploy -> verify.
    assert kinds == [
        ReleaseStepKind.build,
        ReleaseStepKind.smoke,
        ReleaseStepKind.fix,
        ReleaseStepKind.smoke,
        ReleaseStepKind.deploy,
        ReleaseStepKind.verify,
    ]
    # The first smoke result is a documented failure; the second one passes.
    smoke_results = [r for r in report.results if r.kind is ReleaseStepKind.smoke]
    assert smoke_results[0].success is False
    assert smoke_results[0].error == "missing_migration"
    assert smoke_results[1].success is True


def test_verify_failure_aborts_run_without_rollback() -> None:
    """Verify failures are downstream / unrecoverable in this overlay;
    the replanner aborts the run and rollback belongs to the caller."""
    report = run_release("1.5.0", ReleaseEnv.staging)
    assert report.status == "aborted"
    assert report.replanned is True
    last = report.results[-1]
    assert last.kind is ReleaseStepKind.verify
    assert last.success is False
    assert last.error == "downstream_db_unreachable"


def _run_all() -> None:
    """Smoke entry point — run every test as a plain function."""
    test_happy_path_release_succeeds_without_replan()
    print("PASS test_happy_path_release_succeeds_without_replan")
    test_smoke_failure_triggers_fix_step_then_succeeds()
    print("PASS test_smoke_failure_triggers_fix_step_then_succeeds")
    test_verify_failure_aborts_run_without_rollback()
    print("PASS test_verify_failure_aborts_run_without_rollback")
    print("All walkthrough cases passed.")


if __name__ == "__main__":
    _run_all()
