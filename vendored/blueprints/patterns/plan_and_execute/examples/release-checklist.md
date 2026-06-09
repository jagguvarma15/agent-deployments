# Domain example: Release checklist (plan-and-execute)

> Concrete worked example for the [Plan & Execute pattern](../overview.md). The companion mini-project lives in [`release_checklist/`](release_checklist/) and runs offline.

## 1. Recipe context

No validated `agent-deployments` recipe anchors this overlay yet; the shape below is proposed. A future recipe ("release-orchestrator" or similar) would lift the planner + executor + replanner roles into a deployable agent with real CI / smoke / deploy adapters; this overlay is the business-logic shape that recipe would inherit.

The pattern's value lands hardest on workflows where the steps are known and ordered, but failures partway through demand structured remediation, not a full restart. A software release is the archetypal case: the plan is canonical (build -> smoke -> deploy -> verify), step failures often have known fix patterns (a missing migration, a config-flag oversight), and the replanner can insert a targeted fix step before re-running the failed one. The same shape applies to data-pipeline runs, model-deployment workflows, and ops-runbook execution.

Read the framework-agnostic sibling at [`../code/python/plan_and_execute.py`](../code/python/plan_and_execute.py) first for the planner / executor loop; then this overlay for the release-domain shapes and prompts.

## 2. Concrete domain glossary

| Term | Definition |
|------|------------|
| **ReleaseEnv** | Target environment for the release run — `staging` or `production`. |
| **ReleaseStepKind** | The kind of work one step does — `build / smoke / deploy / verify / fix`. The `fix` kind is only inserted by the replanner. |
| **ReleasePlanStep** | One typed step. Carries `id`, `kind`, `target_service`, `description`, optional `tool_hint`, `depends_on`. Mirrors the canonical [`Step`](../schemas/state.py) shape and adds `kind` + `target_service`. |
| **ReleasePlan** | The planner's output — `version`, `env`, `goal`, ordered `steps`, optional `rationale`. Composes with the canonical [`Plan`](../schemas/state.py). |
| **ReleaseStepResult** | One executor outcome — `step_id`, `kind`, `success`, `output`, optional `error`. Wraps the canonical [`ExecutionResult`](../schemas/state.py) shape with the step-kind tag. |
| **ReplanDecision** | The replanner's structured output — `action` (`insert_fix` / `proceed` / `abort`), optional `fix_step`, `rationale`. |

## 3. Concrete data

Three example release runs the orchestrator handles:

```json
{"version": "1.4.2", "env": "staging", "outcome": "succeeded"}
{"version": "1.4.3", "env": "staging", "outcome": "succeeded after replan (missing_migration)"}
{"version": "1.5.0", "env": "staging", "outcome": "aborted at verify (downstream_db_unreachable)"}
```

Corresponding plans (the planner role's output, one shape for all three since the canonical sequence is fixed):

```json
{
  "version": "<v>",
  "env": "staging",
  "goal": "deploy <v> to staging with green smoke + verify.",
  "steps": [
    {"id": "build-web",  "kind": "build",  "target_service": "web", "tool_hint": "ci_adapter",   "depends_on": []},
    {"id": "smoke-web",  "kind": "smoke",  "target_service": "web", "tool_hint": "smoke_runner", "depends_on": ["build-web"]},
    {"id": "deploy-web", "kind": "deploy", "target_service": "web", "tool_hint": "deploy_adapter","depends_on": ["smoke-web"]},
    {"id": "verify-web", "kind": "verify", "target_service": "web", "tool_hint": "verifier",     "depends_on": ["deploy-web"]}
  ]
}
```

And one mid-run replan decision (the `1.4.3` smoke failure path):

```json
{
  "action": "insert_fix",
  "fix_step": {
    "id": "fix-web",
    "kind": "fix",
    "target_service": "web",
    "description": "apply pending migration",
    "depends_on": []
  },
  "rationale": "known fix pattern 'missing_migration'; insert fix before smoke retry."
}
```

## 4. Concrete tool implementations

Full Python in [`release_checklist/tools.py`](release_checklist/tools.py).

- **`CIAdapter.fetch_build(version) -> {sha, artifact, status}`** — wraps `GET https://ci.example.com/builds/{version}`. Mock returns from a small canned table keyed by version; raises `LookupError` for unknown versions so the executor can mark the build step as `failed` rather than crash.
- **`SmokeRunner.run(version, target_service) -> {status, reason?}`** — wraps `POST https://smoke.example.com/run`. Mock honours per-version + per-step failure scenarios in `_SMOKE_FAILURES` so the walkthrough exercises both happy and replan paths. The runner records applied fixes (`record_fix`) so the smoke retry after a fix step passes.
- **`DeployAdapter.deploy(version, target_service, env) -> {status, deployment_id}`** — wraps `POST https://deploy.example.com/release`. Mock records the call so the verifier has something to check.
- **`Verifier.check_health(version, target_service) -> {status, reason?}`** — wraps `GET https://verify.example.com/healthz`. Mock returns `down` for versions in the `_VERIFY_TERMINAL` table.

The mock-body / real-API split is the contract the recipe (when one lands) will pin. Real adapters swap the bodies; call signatures stay constant so the orchestrator code is unchanged.

## 5. Per-role prompts

Full strings in [`release_checklist/prompts.py`](release_checklist/prompts.py). Three roles, each typed input -> typed output:

- **`planner`** — input: `version + ReleaseEnv`. output: `ReleasePlan`. The canonical 4-step sequence is fixed by the prompt; the planner never invents steps. The prompt names the four tool hints so the executor's dispatch is unambiguous.
- **`executor`** — input: one `ReleasePlanStep` at a time plus the build / smoke / deploy context. output: `ReleaseStepResult`. Dispatches on `kind` to the matching tool. Tool exceptions or non-`ok` statuses set `success=False` and populate `error` with one short sentence.
- **`replanner`** — input: a failed `ReleaseStepResult` plus the original plan and remaining steps. output: `ReplanDecision`. Policy: known smoke failure pattern -> insert a fix step; verify failure -> abort (downstream concern); anything else -> abort (planner must re-author).

Sample dialog for `replanner`:

```
[system] You are the replanner. Invoked only on an executor failure...
[user]   Failed step: ReleaseStepResult(step_id="smoke-web", kind="smoke", success=False, error="missing_migration")
         Remaining plan: [deploy-web, verify-web]
[assistant — JSON]
{"action": "insert_fix", "fix_step": {"id": "fix-web", "kind": "fix", ...}, "rationale": "known fix pattern 'missing_migration'; insert fix before smoke retry."}
```

## 6. Decision schemas

Pydantic v2 models in [`release_checklist/schemas.py`](release_checklist/schemas.py):

```python
class ReleasePlan(BaseModel):
    version: str
    env: ReleaseEnv             # staging | production
    goal: str
    steps: list[ReleasePlanStep]
    rationale: str | None = None


class ReleasePlanStep(BaseModel):
    id: str
    kind: ReleaseStepKind        # build | smoke | deploy | verify | fix
    target_service: str
    description: str
    tool_hint: str | None = None
    depends_on: list[str] = []


class ReleaseStepResult(BaseModel):
    step_id: str
    kind: ReleaseStepKind
    success: bool
    output: str
    error: str | None = None


class ReplanDecision(BaseModel):
    action: str                  # insert_fix | proceed | abort
    fix_step: ReleasePlanStep | None = None
    rationale: str
```

These compose with the canonical Plan & Execute state in [`../schemas/state.py`](../schemas/state.py): a recipe-level `PlanExecuteState.execution_results` carries `ExecutionResult` per step; this overlay's `ReleaseStepResult` is a typed view of that shape with the domain's `kind` tag added.

## 7. End-to-end walkthrough

Three traces from `run_release(...)`:

### Happy path (`1.4.2`)

1. **Caller invokes** `run_release("1.4.2", ReleaseEnv.staging)`. `main.py:run_release`.
2. **Planner.** `_plan(version, env)` produces the canonical 4-step plan against the `web` service: build -> smoke -> deploy -> verify.
3. **Executor walks the queue.** Each step dispatches by `kind`. Build returns `green (sha=sha:abc123)`; smoke returns `ok`; deploy records `dep_1.4.2_web_staging`; verify returns `ok`.
4. **Terminal status.** No failures -> `ReleaseRunReport(status="succeeded", replanned=False)`.

### Replan path (`1.4.3`)

1. **Same plan, same start.** Build returns green.
2. **Smoke fails.** `SmokeRunner.run` returns `{"status": "fail", "reason": "missing_migration"}`. The executor sets `success=False, error="missing_migration"`.
3. **Replanner.** `_replan(failed, plan)` sees the known fix pattern -> `ReplanDecision(action="insert_fix", fix_step=<fix-web kind=fix>)`. The orchestrator splices the fix step in front of the failed smoke step in the queue.
4. **Fix + retry.** Executor runs the fix step (`SmokeRunner.record_fix("web")`), then re-runs smoke; the recorded fix flips the canned failure to `ok`.
5. **Deploy + verify proceed.** Same as the happy path. Terminal status `succeeded`, `replanned=True`.

### Abort path (`1.5.0`)

1. **Same plan, build / smoke / deploy all pass.**
2. **Verify fails.** `Verifier.check_health` returns `{"status": "down", "reason": "downstream_db_unreachable"}`. The executor sets `success=False, error="downstream_db_unreachable"`.
3. **Replanner.** Verify failures are unrecoverable in this overlay -> `ReplanDecision(action="abort", rationale="verify failed; rollback belongs to the caller.")`.
4. **Terminal status.** `ReleaseRunReport(status="aborted", replanned=True)`. The caller (a CI job or a release dashboard) initiates rollback.

The test suite ([`release_checklist/test_walkthrough.py`](release_checklist/test_walkthrough.py)) covers all three terminal states.

## Run it

```bash
cd patterns/plan_and_execute/examples/release_checklist
uv run --with pydantic python -m patterns.plan_and_execute.examples.release_checklist.main
# or
uv run --with pydantic --with pytest python -m pytest test_walkthrough.py -v
```
