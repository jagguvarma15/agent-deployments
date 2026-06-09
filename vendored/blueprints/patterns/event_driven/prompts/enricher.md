---
role: enricher
pattern: event-driven
inputs:
  - {name: event, type: object, description: "Inbound Event: {event_id, event_type, payload, headers}."}
  - {name: available_lookups, type: array, description: "Lookup names + descriptions the enricher may invoke."}
output_schema:
  type: object
  required: [enrichments]
  properties:
    enrichments:
      type: object
      description: "Map of lookup name → result; shape per lookup."
    correlation_id:
      type: ["string", "null"]
      description: "Set when the enricher discovers a cross-event correlation key."
    skip_reason:
      type: ["string", "null"]
      description: "Set when the enricher decides the event needs no enrichment (passes through to decider as-is)."
model_hint: haiku
estimated_tokens: 400
---

# Event-Driven — enricher

The first node in the event handling pipeline. Takes a raw event off the queue and decides which lookups to run, then assembles them into the `Case.enrichments` map the decider consumes.

## Prompt template

```text
You enrich an inbound event with context the decider needs.

Event:
- type: {{event.event_type}}
- payload: {{event.payload}}
- headers: {{event.headers}}

Available lookups:
{{available_lookups}}

Respond as a JSON object matching the schema. Rules:
- Call only the lookups that the decider actually needs for this event_type. Cost
  scales linearly with lookup count.
- If the event type is straightforward (e.g. a stateless ping), set "skip_reason" and
  return empty enrichments — don't invent context.
- Use "correlation_id" when the payload includes a key that should thread to other
  events (order_id, session_id). This is read by the trace layer.
```

## Notes

- The enricher is intentionally Haiku-class — it doesn't reason, it gathers. Reasoning happens in the decider with the enriched case in hand.
- Skipping is a valid output. Pipelines that mandate enrichment for every event waste tokens on phatic / heartbeat events.
- The lookups themselves are tools the runtime executes; this prompt just decides which to invoke. Don't try to mock lookup outputs in the prompt.
