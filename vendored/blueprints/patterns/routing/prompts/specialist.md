---
role: specialist
pattern: routing
inputs:
  - {name: request, type: string, description: "Original user request the router classified."}
  - {name: route_name, type: string, description: "Which route was picked; selects this specialist's persona."}
  - {name: route_context, type: object, description: "Route-specific scratch data (tools, knowledge base id, escalation rules)."}
output_schema:
  type: object
  required: [response, escalate]
  properties:
    response:
      type: string
      description: "The specialist's answer to the user."
    escalate:
      type: boolean
      description: "True when this specialist couldn't handle the request and a human or different route should take over."
    escalate_reason:
      type: ["string", "null"]
      description: "Required when escalate is true; surfaced to the escalation queue."
model_hint: sonnet
estimated_tokens: 800
---

# Routing — specialist (generic)

A generic specialist prompt parameterized by which route was picked. Use this when your routes don't differ enough in tone / tools / depth to warrant per-route prompt files. Otherwise fork into `specialist-<route>.md` siblings.

## Prompt template

```text
You are the {{route_name}} specialist. Your scope is bounded by the route context below;
do not attempt requests outside it.

Route context:
{{route_context}}

User request: {{request}}

Respond as a JSON object matching the schema. Rules:
- Stay strictly within your route's scope. If the request has drifted, set "escalate": true
  with a one-line "escalate_reason".
- Be concrete. Cite specific values from the route context where relevant.
- Do not invent tools or knowledge not described in the route context.
```

## Notes

- The `escalate` flag is what makes the routing pattern recoverable — without it, misrouted requests get bad answers silently. Always log escalations for router-quality eval.
- `route_context` is intentionally loose-typed (`object`) because each route brings its own shape (tools, KB id, escalation queue). The runtime hydrates it per route before calling.
- Keep the prompt format identical across all routes that share this file; per-route persona / tone differences live in `route_context`.
