---
role: planner
pattern: plan_and_execute
inputs:
  - {name: goal, type: string, description: "Objective the plan addresses."}
  - {name: context, type: ["string", "null"], description: "Optional prior context or constraints."}
  - {name: available_tools, type: array, description: "Tools the executor can call; lets the planner choose tool_hints."}
  - {name: max_steps, type: integer, description: "Hard cap on plan length."}
output_schema:
  type: object
  required: [goal, steps]
  properties:
    goal:
      type: string
      description: "Restated objective; lets the planner clarify ambiguous input."
    steps:
      type: array
      minItems: 1
      items:
        type: object
        required: [id, description]
        properties:
          id: {type: string, description: "Stable id (e.g. 'step-1')."}
          description: {type: string}
          tool_hint:
            type: ["string", "null"]
            description: "Optional suggested tool; executor may override."
          depends_on:
            type: array
            items: {type: string}
            description: "Step ids that must complete before this one runs."
    rationale:
      type: ["string", "null"]
      description: "Optional explanation of the decomposition."
model_hint: sonnet
estimated_tokens: 800
---

# Plan & Execute — planner

Decomposes a goal into an ordered, executable plan. Runs once at the start (and again on replan). Sonnet-class — planning is reasoning-heavy.

## Prompt template

```text
You are a planner. Decompose this goal into a sequence of executable steps.

Goal: {{goal}}
Constraints / prior context: {{context}}

Available tools (the executor will call these):
{{available_tools}}

Cap: at most {{max_steps}} steps.

Respond as a JSON object matching the schema. Rules:
- Every step must be a concrete, verifiable action — not "consider X" or "think about Y".
- Use "tool_hint" when one of the available tools is the obvious choice; leave it null
  when the executor should choose.
- Use "depends_on" only when a step truly cannot run until another completes. Independent
  steps with empty depends_on run in parallel.
- "rationale" is optional but useful for replans — it makes failure modes legible.
```

## Notes

- The planner doesn't execute — it just emits the plan. Resist the urge to include "checkpoint" steps that ask the planner to think again; those belong to the reflector.
- For tasks under ~5 steps, the planner overhead exceeds the benefit. Use ReAct instead.
- Replan loops re-invoke this prompt with `context` extended by the failure summary. Keep that addition < 500 tokens or the planner ignores it.
