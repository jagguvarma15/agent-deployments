---
role: decider
pattern: event-driven
inputs:
  - {name: case, type: object, description: "Enriched Case: {event, enrichments, correlation_id}."}
  - {name: policy, type: object, description: "Business rules: thresholds, allowed actions, escalation criteria."}
  - {name: available_actions, type: array, description: "List of {name, description, args_schema} the actor can perform."}
output_schema:
  type: object
  required: [action, reasoning]
  properties:
    action:
      type: string
      description: "Name of the action to take; must match an entry in available_actions OR be 'noop' / 'dlq'."
    args:
      type: object
      description: "Args matching the chosen action's schema; empty for noop/dlq."
    reasoning:
      type: string
      description: "Why this action — surfaced in audit logs and incident reviews."
    recommend_dlq:
      type: boolean
      description: "True when the decider can't safely decide; routes to dead-letter queue for human review."
    confidence:
      type: ["number", "null"]
      minimum: 0
      maximum: 1
      description: "Optional 0..1 confidence; downstream may DLQ below threshold."
model_hint: sonnet
estimated_tokens: 800
---

# Event-Driven — decider

The reasoning step. Takes one enriched Case + policy, decides which action the actor should perform (or routes to DLQ). The single most consequential prompt in the pipeline — its mistakes touch users.

## Prompt template

```text
You decide what to do with one enriched event.

Case:
{{case}}

Business policy:
{{policy}}

Available actions:
{{available_actions}}

Respond as a JSON object matching the schema. Rules:
- "action" must be exactly one of the available_actions, OR "noop" (no action needed),
  OR "dlq" (cannot decide safely). Don't invent action names.
- "reasoning" is required for every decision — auditors read these.
- Set "recommend_dlq": true when policy is ambiguous, enrichments are insufficient, or
  the action would be high-impact (refund > threshold, account closure, …).
- "confidence" is your honest estimate. Don't optimize the number; downstream code
  routes low-confidence decisions to DLQ regardless of your action.
```

## Notes

- The DLQ exit is non-negotiable. Without it the decider learns to push through low-confidence calls and breaks audit. Eval suites must include ambiguous cases that should DLQ.
- This prompt has no memory of prior cases — each is independent. Cross-event reasoning belongs upstream (in enricher's `correlation_id`) or downstream (in actor's emitted events).
- Sonnet is the floor. Haiku deciders make policy errors at material rates. Opus is justified for high-impact domains (finance, healthcare) where each decision can move dollars.
