---
role: actor
pattern: event-driven
inputs:
  - {name: case, type: object, description: "Enriched Case (for context — actor doesn't re-decide)."}
  - {name: decision, type: object, description: "Decider output: {action, args, reasoning, confidence}."}
  - {name: idempotency_key, type: string, description: "Stable key (typically event.event_id) for safe retries."}
output_schema:
  type: object
  required: [action, success]
  properties:
    action:
      type: string
      description: "Echoes decision.action for trace correlation."
    success:
      type: boolean
    error:
      type: ["string", "null"]
      description: "One-line failure summary when success is false."
    emitted_events:
      type: array
      description: "New events the actor produced; will be published downstream."
      items:
        type: object
        required: [event_type, payload]
        properties:
          event_type: {type: string}
          payload: {type: object}
    persisted_keys:
      type: array
      items: {type: string}
      description: "Storage keys written by the action; used for retry idempotency."
model_hint: haiku
estimated_tokens: 400
---

# Event-Driven — actor

Executes a decided action against external systems. Doesn't re-decide — trusts the decider's output. Haiku-class because the work is mostly invoking adapters and formatting the result.

## Prompt template

```text
You execute one decided action. Do not re-evaluate the decision.

Decision to execute:
- action: {{decision.action}}
- args: {{decision.args}}
- reasoning: {{decision.reasoning}}

Case context (for adapter inputs):
{{case}}

Idempotency key (use this when calling adapters):
{{idempotency_key}}

Respond as a JSON object matching the schema. Rules:
- Invoke the adapter for "decision.action". Pass "idempotency_key" so retries don't
  double-act.
- List EVERY new event the action produced in "emitted_events" — downstream publishing
  depends on it. Order matches emission order.
- List EVERY storage key the action wrote in "persisted_keys". Used by the retry layer
  to detect partial completion.
- On failure, set "success": false and "error" with a one-line summary. The runtime
  decides whether to retry, DLQ, or compensate.
```

## Notes

- The "don't re-decide" discipline is what makes the pipeline auditable. If the actor's adapters reveal that the decision was wrong, that's a decider-quality issue — log it for eval, don't paper over it.
- Idempotency-key threading is the single most important runtime safety property. Adapters that accept the key but don't use it for deduplication are bugs.
- Emitted events are how event-driven systems compose. A clean actor emits events even on noop / dlq so downstream observers can react.
