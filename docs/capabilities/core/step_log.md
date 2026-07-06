---
id: core.step_log
kind: core
implements:
  port: core
  interface_version: "1.0"
layer: agent
provides: [step_log, run_log]
env_vars: []
docker: null
probe: null
bootstrap_step: null
provisioning_time: instant
cost_tier: free
card:
  name: Step log
  description: "A serializable step-log — the agent's run state as an append-only, secret-redacted jsonl event log under .agent/runs/. Pause / resume / retry / trace. The T2 workflow substrate."
  capabilities_provided: [step_log, run_log]
  required_credentials: []
emit_files:
  - source: templates/step_log/steplog.py
    dest: agent/steplog.py
deploy_configs: []
docs: |
  Emits agent/steplog.py: a StepStatus enum, a StepState record, and a
  run-scoped StepLog sink that appends one JSON event per line to
  .agent/runs/<run_id>/events.jsonl (every string redacted first). The log is
  the state — replay_states() folds the events back into per-step states, so a
  workflow agent can pause, resume, retry a failed step, or be traced. Do NOT
  reinvent the sink or the run-id scheme — import it: `from agent.steplog import
  StepLog, StepStatus`. Wrap a run in `with StepLog() as log:` and bracket each
  step with log.start(id) / log.finish(state, status). The .agent/runs/ tree is
  runtime output — it should be gitignored (the scaffold does this by default),
  while .agent/spec.md stays committed.
tags: [core, step-log, state, resume, observability]
when_to_load: "recipe tier is T2 or higher (the tier preset seeds core.step_log)"
---

# Core: Step log

The workflow substrate emitted at the **T2** tier. It makes a run's state an
append-only, secret-redacted event log on disk, so a multi-step agent can pause,
resume, retry a failed step, or be traced after the fact — without standing up a
database. It is the slimmed sibling of the scaffold's own orchestrator state and
run-log jsonl sink.

## Emitted files

`emit_files` copies one self-contained module into the project:

| File | Role |
|---|---|
| `agent/steplog.py` | `StepStatus` + `StepState` + `StepLog` (the run-scoped jsonl sink) + `replay_states` (fold events back into state). Standard library only. |

The copier never overwrites a file the model emitted at the same path, so a
recipe can specialize the sink while inheriting the contract.

## Wiring

Wrap a run in the sink and bracket each step:

```python
from agent.steplog import StepLog, StepStatus

with StepLog() as log:            # writes .agent/runs/<id>/events.jsonl
    step = log.start("fetch")
    try:
        ...                       # do the work
        log.finish(step, StepStatus.DONE)
    except Exception as exc:
        log.finish(step, StepStatus.FAILED, error=str(exc))
```

On the next run, `replay_states(events_path)` reconstructs each step's state — a
step left RUNNING (a crash mid-step) comes back PENDING, so a resume re-runs it.
That is the pause / resume / retry primitive: the jsonl is the durable state.

## See also

- Reference implementation: the `step_log` primitive in agent-blueprints
  (`primitives/step_log/`) — the framework-agnostic schema + demo this slims down.
- The `.agent/runs/` tree is runtime output and should be gitignored; the
  generated `.agent/spec.md` records the tier that seeded this capability.
