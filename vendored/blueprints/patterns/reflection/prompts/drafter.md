---
role: drafter
pattern: reflection
inputs:
  - {name: goal, type: string, description: "What the drafter is trying to produce."}
  - {name: iteration, type: integer, description: "0-indexed draft number; 0 is the initial draft."}
  - {name: prior_drafts, type: array, description: "Previous Draft entries (iteration, content, notes)."}
  - {name: prior_critiques, type: array, description: "Previous Critique entries (iteration, issues, suggestions)."}
output_schema:
  type: object
  required: [iteration, content]
  properties:
    iteration:
      type: integer
      minimum: 0
      description: "Matches the input iteration; included for downstream correlation."
    content:
      type: string
      description: "The draft itself; format is task-specific (essay, code, plan, …)."
    notes:
      type: ["string", "null"]
      description: "Optional commentary on changes from the prior draft; helps the critic understand intent."
model_hint: sonnet
estimated_tokens: 1200
---

# Reflection — drafter

Produces one draft of the goal. On iteration 0 there's no prior critique; on later iterations the drafter must address every issue the critic raised before exploring new ground.

## Prompt template

```text
You are drafting toward this goal:

{{goal}}

This is iteration {{iteration}}.

{% if prior_drafts %}
Your most recent draft:
{{prior_drafts[-1].content}}

The critic's response to it:
- Issues: {{prior_critiques[-1].issues}}
- Suggestions: {{prior_critiques[-1].suggestions}}
{% endif %}

Produce a JSON object matching the schema. Rules:
- Address every issue the critic raised. Don't pretend issues away with new structure.
- Don't regress on previously-accepted aspects of the draft.
- Use "notes" to flag intentional deviations from the critic's suggestions.
```

## Notes

- The drafter sees only the most recent critique — earlier critiques are intentionally dropped. If you want long-memory critique, accumulate them in `notes` instead of feeding the full history.
- Setting `notes` is optional but encouraged on iteration 2+; it gives the critic a fairer evaluation context and helps eval debugging.
- For long-form outputs (essays, code), Sonnet is the sweet spot. Switch to Opus only when iteration count consistently exceeds 3 — that signals the drafter is undermatched.
