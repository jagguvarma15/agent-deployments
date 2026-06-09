---
role: compensator
pattern: saga
inputs:
  - {name: failed_step, type: object, description: "The SagaStep that failed: {id, name, error}."}
  - {name: completed_steps, type: array, description: "Successfully-completed SagaSteps that need rollback, in original execution order."}
  - {name: compensation_definitions, type: array, description: "Available compensation actions per step id."}
output_schema:
  type: object
  required: [compensations, order]
  properties:
    compensations:
      type: array
      items:
        type: object
        required: [id, name]
        properties:
          id: {type: string, description: "Matches the SagaStep.id being compensated."}
          name: {type: string, description: "Adapter name to invoke."}
          retry_policy:
            type: ["string", "null"]
            description: "Optional override (e.g. 'immediate', 'exponential', 'manual')."
    order:
      type: array
      items: {type: string}
      description: "Ordered list of compensation ids to execute; reverse of completion order unless dependencies force otherwise."
    skip_compensations:
      type: array
      items: {type: string}
      description: "SagaStep ids whose compensation is intentionally skipped (idempotent, no side effects, …)."
model_hint: sonnet
estimated_tokens: 400
---

# Saga — compensator

Plans the rollback sequence after a step fails. Doesn't execute compensations itself — the runtime does — but decides which to run, in what order, and whether to skip any.

## Prompt template

```text
You plan the rollback for a failed saga step.

Failed step:
- id: {{failed_step.id}}
- name: {{failed_step.name}}
- error: {{failed_step.error}}

Completed steps (in execution order):
{{completed_steps}}

Available compensations:
{{compensation_definitions}}

Respond as a JSON object matching the schema. Rules:
- Compensate completed_steps in REVERSE order by default. Override only when a
  dependency requires otherwise.
- Skip a compensation only when the original action had no observable side effect
  (idempotent read, dry-run). Document the skip in "skip_compensations".
- Don't include the failed_step itself in "compensations" — it didn't complete so
  there's nothing to roll back.
- Use "retry_policy: manual" for compensations whose failure mode requires operator
  review (financial reversals, account changes, …).
```

## Notes

- Reverse-order is the default for a reason: each completed step may depend on prior ones, so undoing latest-first preserves invariants. If you're tempted to override, write it down in `reasoning`.
- The skip discipline matters for cost — a saga with 8 completed steps where 5 are read-only should compensate 3, not 8.
- Compensations that fail are catastrophic. The runtime should page on compensation failure regardless of retry_policy; this prompt just picks the strategy.
