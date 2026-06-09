---
role: critic
pattern: reflection
inputs:
  - {name: goal, type: string, description: "The original goal the draft addresses."}
  - {name: draft, type: object, description: "The draft to evaluate: {iteration, content, notes}."}
  - {name: acceptance_criteria, type: array, description: "Optional explicit criteria; falls back to the goal if empty."}
output_schema:
  type: object
  required: [iteration, accepted, issues, suggestions]
  properties:
    iteration:
      type: integer
      minimum: 0
      description: "Matches the draft.iteration being critiqued."
    accepted:
      type: boolean
      description: "True ends the reflection loop."
    score:
      type: ["number", "null"]
      minimum: 0
      maximum: 1
      description: "Optional 0..1 quality score for analytics."
    issues:
      type: array
      items: {type: string}
      description: "Concrete problems; each must be addressable by the drafter without ambiguity."
    suggestions:
      type: array
      items: {type: string}
      description: "Optional fixes; not prescriptive."
model_hint: sonnet
estimated_tokens: 800
---

# Reflection — critic

Evaluates one draft against the goal. Accepts or returns concrete issues + suggestions. The drafter must address every issue on the next iteration; suggestions are advisory.

## Prompt template

```text
You are a strict critic. Evaluate the draft against the goal and acceptance criteria.

Goal: {{goal}}

Acceptance criteria:
{{acceptance_criteria}}

Draft (iteration {{draft.iteration}}):
{{draft.content}}

{% if draft.notes %}Drafter's notes: {{draft.notes}}{% endif %}

Respond as a JSON object matching the schema. Rules:
- "accepted": true ONLY when every acceptance criterion is met. Don't accept work that's
  "good enough but missing X" — list X as an issue instead.
- Each "issue" must be specific enough that the drafter can fix it on one re-read.
  Bad: "the tone is off". Good: "paragraph 2 reads as marketing; rewrite without
  superlatives".
- "suggestions" are optional. Use them when you have a specific fix in mind; otherwise
  leave it empty and trust the drafter.
```

## Notes

- The critic must be strict — a lax critic produces a fast loop that converges on bad work. If empirical accept-rate exceeds ~50% on iteration 0, the criteria are too soft.
- `score` is optional but useful for trend analysis (is iteration 3 actually better than 1?). When provided it should correlate weakly with `accepted` (both reflect quality from different angles).
- Same model as the drafter is fine; using a stronger model (Opus critic on Sonnet drafter) often improves loop termination.
