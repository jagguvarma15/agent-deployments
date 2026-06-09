---
role: coordinator
pattern: saga
inputs:
  - {name: saga_id, type: string, description: "Stable id used in logs and idempotency."}
  - {name: steps_definition, type: array, description: "Ordered list of {id, name, description} for the forward path."}
  - {name: completed_steps, type: array, description: "SagaSteps already executed (status, output, error)."}
  - {name: failure_context, type: ["object", "null"], description: "Set when a step failed; contains failure_step_id + adapter error."}
output_schema:
  type: object
  required: [next_action, reasoning]
  properties:
    next_action:
      type: string
      enum: [run_step, compensate, complete, abort]
      description: "run_step: execute the next forward step. compensate: roll back completed steps. complete: saga done. abort: hard fail without compensation."
    step_id:
      type: ["string", "null"]
      description: "Required when next_action is run_step; identifies which step to execute next."
    reasoning:
      type: string
      description: "Why this choice — included in saga audit log."
    skip_steps:
      type: array
      items: {type: string}
      description: "Step ids to skip if the coordinator decides they're no longer needed (e.g. preconditions failed)."
model_hint: sonnet
estimated_tokens: 500
---

# Saga — coordinator

The state machine. Decides each round whether to run the next forward step, kick off compensation, complete, or hard-abort. Sonnet-class because the decision depends on multiple signals (completed_steps, failure_context, policy).

## Prompt template

```text
You coordinate a distributed transaction. Pick the next action.

Saga: {{saga_id}}

Plan (forward steps):
{{steps_definition}}

Completed so far:
{{completed_steps}}

Failure context (null if no step has failed):
{{failure_context}}

Respond as a JSON object matching the schema. Rules:
- "run_step" when the prior step succeeded and there's another to run. Set "step_id"
  to the next unexecuted step in steps_definition.
- "compensate" when failure_context is set. The compensator will roll back completed_steps
  in reverse order.
- "complete" when every step in steps_definition has status "succeeded" or "skipped".
- "abort" only when compensation is impossible AND completion isn't reachable — this is
  the worst outcome and triggers operator paging. Use sparingly.
- "skip_steps" lets you bypass steps whose preconditions no longer hold (e.g. user
  cancelled mid-flight). Use rarely; document each skip in "reasoning".
```

## Notes

- The coordinator is stateless — it sees the full saga state every round. This lets you resume after a process crash by re-invoking with the persisted state.
- `compensate` and `complete` are terminal-ish; the runtime drives compensation steps separately (see `compensator.md`).
- `abort` should always page. Sagas that abort silently leak partial state and corrupt data. Keep abort eval coverage tight.
