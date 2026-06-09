"""End-to-end walkthrough wiring for the release-checklist overlay.

Composes the schemas, tools, and prompts into a ``run_release`` entry
point that takes a version + env and produces a list of
:class:`ReleaseStepResult` entries plus a final terminal status
(`succeeded` / `aborted`). The planner, executor, and replanner roles
are deterministic stubs here (so the walkthrough runs offline);
production swaps each for an ``anthropic`` ``Agent`` call against the
corresponding system prompt.

Pattern this composes: Plan & Execute. See ``../../overview.md`` for the
framework-agnostic shape and ``../../code/python/plan_and_execute.py``
for the canonical sibling implementation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .schemas import (
    ReleaseEnv,
    ReleasePlan,
    ReleasePlanStep,
    ReleaseStepKind,
    ReleaseStepResult,
    ReplanDecision,
)
from .tools import CIAdapter, DeployAdapter, SmokeRunner, Verifier

log = logging.getLogger(__name__)


# ── planner role (stub for the LLM call) ─────────────────────────────────────


def _plan(version: str, env: ReleaseEnv) -> ReleasePlan:
    """Produce the canonical 4-step plan against the `web` service.

    The planner prompt fixes the sequence; here we encode the same
    sequence deterministically so the walkthrough runs offline.
    """
    target = "web"
    steps = [
        ReleasePlanStep(
            id=f"build-{target}",
            kind=ReleaseStepKind.build,
            target_service=target,
            description=f"confirm build for {version} is green",
            tool_hint="ci_adapter",
        ),
        ReleasePlanStep(
            id=f"smoke-{target}",
            kind=ReleaseStepKind.smoke,
            target_service=target,
            description=f"run smoke suite against {target}",
            tool_hint="smoke_runner",
            depends_on=[f"build-{target}"],
        ),
        ReleasePlanStep(
            id=f"deploy-{target}",
            kind=ReleaseStepKind.deploy,
            target_service=target,
            description=f"deploy {version} to {env.value}",
            tool_hint="deploy_adapter",
            depends_on=[f"smoke-{target}"],
        ),
        ReleasePlanStep(
            id=f"verify-{target}",
            kind=ReleaseStepKind.verify,
            target_service=target,
            description=f"probe post-deploy health for {target}",
            tool_hint="verifier",
            depends_on=[f"deploy-{target}"],
        ),
    ]
    return ReleasePlan(
        version=version,
        env=env,
        goal=f"deploy {version} to {env.value} with green smoke + verify.",
        steps=steps,
        rationale="canonical build -> smoke -> deploy -> verify sequence",
    )


# ── executor role (stub for the LLM call) ────────────────────────────────────


@dataclass
class _Executor:
    """Runs one step, dispatching by kind. Holds the shared adapter state."""

    ci: CIAdapter = field(default_factory=CIAdapter)
    smoke: SmokeRunner = field(default_factory=SmokeRunner)
    deploy: DeployAdapter = field(default_factory=DeployAdapter)
    verify: Verifier = field(default_factory=Verifier)

    def run(self, step: ReleasePlanStep, plan: ReleasePlan) -> ReleaseStepResult:
        try:
            if step.kind is ReleaseStepKind.build:
                info = self.ci.fetch_build(plan.version)
                return ReleaseStepResult(
                    step_id=step.id,
                    kind=step.kind,
                    success=True,
                    output=f"build {plan.version} green (sha={info['sha']})",
                )
            if step.kind is ReleaseStepKind.smoke:
                result = self.smoke.run(plan.version, step.target_service)
                ok = result["status"] == "ok"
                return ReleaseStepResult(
                    step_id=step.id,
                    kind=step.kind,
                    success=ok,
                    output=f"smoke {result['status']} for {step.target_service}",
                    error=None if ok else result.get("reason"),
                )
            if step.kind is ReleaseStepKind.deploy:
                info = self.deploy.deploy(plan.version, step.target_service, plan.env)
                return ReleaseStepResult(
                    step_id=step.id,
                    kind=step.kind,
                    success=True,
                    output=f"deployed {plan.version} to {plan.env.value} as {info['deployment_id']}",
                )
            if step.kind is ReleaseStepKind.verify:
                result = self.verify.check_health(plan.version, step.target_service)
                ok = result["status"] == "ok"
                return ReleaseStepResult(
                    step_id=step.id,
                    kind=step.kind,
                    success=ok,
                    output=f"verify {result['status']} for {step.target_service}",
                    error=None if ok else result.get("reason"),
                )
            if step.kind is ReleaseStepKind.fix:
                # The fix step is inserted by the replanner. The executor
                # applies the remediation and records it with the smoke
                # runner so the smoke retry passes.
                self.smoke.record_fix(step.target_service)
                return ReleaseStepResult(
                    step_id=step.id,
                    kind=step.kind,
                    success=True,
                    output=f"applied fix for {step.target_service}",
                )
        except LookupError as exc:
            return ReleaseStepResult(
                step_id=step.id,
                kind=step.kind,
                success=False,
                output="",
                error=str(exc),
            )
        # Should be unreachable; the enum covers every kind.
        return ReleaseStepResult(
            step_id=step.id,
            kind=step.kind,
            success=False,
            output="",
            error=f"unknown step kind {step.kind}",
        )


# ── replanner role (stub for the LLM call) ───────────────────────────────────


def _replan(failed: ReleaseStepResult, plan: ReleasePlan) -> ReplanDecision:
    # Verify failures are unrecoverable in this overlay.
    if failed.kind is ReleaseStepKind.verify:
        return ReplanDecision(
            action="abort",
            rationale=f"verify failed ({failed.error}); rollback belongs to the caller.",
        )
    # Known smoke failure pattern -> insert a fix step.
    if failed.kind is ReleaseStepKind.smoke and failed.error == "missing_migration":
        target = next(step.target_service for step in plan.steps if step.id == failed.step_id)
        return ReplanDecision(
            action="insert_fix",
            fix_step=ReleasePlanStep(
                id=f"fix-{target}",
                kind=ReleaseStepKind.fix,
                target_service=target,
                description="apply pending migration",
                tool_hint=None,
            ),
            rationale=f"known fix pattern '{failed.error}'; insert fix before smoke retry.",
        )
    return ReplanDecision(
        action="abort",
        rationale=f"no known remediation for {failed.kind.value} failure ({failed.error}).",
    )


# ── orchestrator: run one release end-to-end ─────────────────────────────────


@dataclass
class ReleaseRunReport:
    """Wrap-up for one release run."""

    plan: ReleasePlan
    results: list[ReleaseStepResult]
    status: str  # "succeeded" | "aborted"
    replanned: bool = False


def run_release(version: str, env: ReleaseEnv = ReleaseEnv.staging) -> ReleaseRunReport:
    """Plan, then walk each step; replan on failure."""

    plan = _plan(version, env)
    executor = _Executor()
    results: list[ReleaseStepResult] = []
    replanned = False
    # Track the steps remaining as a queue so the replanner can splice in
    # a fix step ahead of the failed step's retry.
    queue: list[ReleasePlanStep] = list(plan.steps)
    replans = 0
    max_replans = plan.steps and 2  # cap matches the canonical PlanExecuteState default.

    while queue:
        step = queue.pop(0)
        result = executor.run(step, plan)
        results.append(result)
        if result.success:
            continue
        if replans >= max_replans:
            return ReleaseRunReport(plan=plan, results=results, status="aborted", replanned=replanned)
        decision = _replan(result, plan)
        replanned = True
        if decision.action == "insert_fix" and decision.fix_step is not None:
            # Insert the fix step, then re-enqueue the failed step.
            queue.insert(0, step)
            queue.insert(0, decision.fix_step)
            replans += 1
            continue
        # `proceed` is reserved for non-fatal failures; the overlay's
        # current policy treats every other branch as abort.
        return ReleaseRunReport(plan=plan, results=results, status="aborted", replanned=replanned)

    return ReleaseRunReport(plan=plan, results=results, status="succeeded", replanned=replanned)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for version in ["1.4.2", "1.4.3", "1.5.0"]:
        report = run_release(version)
        print(f"{version} -> status={report.status} replanned={report.replanned}")
        for r in report.results:
            print(f"  [{r.kind.value:7}] {r.step_id:14} success={r.success} output={r.output}")
