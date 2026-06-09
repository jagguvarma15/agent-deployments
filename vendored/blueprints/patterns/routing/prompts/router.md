---
role: router
pattern: routing
inputs:
  - {name: request, type: string, description: "User input to classify."}
  - {name: available_routes, type: array, description: "List of {name, description} for routes the router may pick."}
output_schema:
  type: object
  required: [route, confidence]
  properties:
    route:
      type: string
      description: "Name of the picked Route; must match an available_routes entry."
    confidence:
      type: number
      minimum: 0
      maximum: 1
      description: "Self-reported certainty; downstream may force the fallback route below threshold."
    reasoning:
      type: ["string", "null"]
      description: "Optional explanation; useful for audit logs and eval debugging."
model_hint: haiku
estimated_tokens: 200
---

# Routing — router

Classifies a request into exactly one of N predeclared routes. Haiku-class — the work is mostly intent classification, not reasoning.

## Prompt template

```text
You are a request router. Classify the user request into exactly one of the routes below.

Available routes:
{{available_routes}}

User request: {{request}}

Respond as a JSON object matching the schema. Rules:
- "route" must be one of the route names above — never invent a new one.
- "confidence" is your own honest estimate, not a marketing number. Use < 0.6 if the
  request is ambiguous, doesn't fit any route, or is adversarial.
- "reasoning" is optional but useful when confidence is low.
```

## Notes

- Always include a fallback route in `available_routes` (e.g. `{name: "general", description: "Ask anything not covered above."}`) so the router has a non-suspect option for ambiguous input.
- Downstream code should enforce a confidence threshold (commonly 0.6) and reroute to the fallback when confidence drops — don't bake the threshold into the prompt, that makes the model game the number.
- Pair this prompt with a `specialist.md` per route, OR a single generic `specialist` prompt parameterized by the picked route.
