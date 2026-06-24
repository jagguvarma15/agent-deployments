---
role: reflector
pattern: plan_and_execute
inputs:
  - {name: original_goal, type: string, description: "The goal the plan was supposed to achieve."}
  - {name: plan, type: object, description: "The current Plan ({goal, steps, rationale})."}
  - {name: execution_results, type: array, description: "ExecutionResult per completed step (success, output, error)."}
  - {name: replans_remaining, type: integer, description: "How many replans the loop will still allow."}
output_schema:
  type: object
  required: [decision]
  properties:
    decision:
      type: string
      enum: [done, continue, replan]
      description: "done: synthesize final_answer; continue: keep executing; replan: invoke planner again."
    final_answer:
      type: ["string", "null"]
      description: "Required when decision == done."
    replan_focus:
      type: ["string", "null"]
      description: "Required when decision == replan; sent to the planner as additional context."
    reasoning:
      type: string
      description: "Why this decision — included in the trace and surfaced in eval failures."
  required: [decision, reasoning]
model_hint: sonnet
estimated_tokens: 600
---

# Plan & Execute — reflector

Runs after each batch of step executions (or at the end) to decide whether the plan is done, should continue, or needs replanning. The escape hatch that keeps the loop honest.

## Prompt template

```text
You evaluate plan progress and decide what happens next.

Original goal: {{original_goal}}

Plan rationale: {{plan.rationale}}

Steps so far:
{{execution_results}}

Replans remaining: {{replans_remaining}}

Respond as a JSON object matching the schema. Rules:
- "done" only when the original goal is actually achieved — not when steps merely succeeded.
- "continue" when steps are in flight and no replan is needed. Don't return "continue" if
  every step has completed; pick done or replan.
- "replan" only when execution_results reveal that the plan's structure is wrong (a step
  is impossible, an assumption was false, …). Include a "replan_focus" describing what
  the new plan should account for. If replans_remaining is 0, fall back to "done" with a
  partial final_answer instead.
- "reasoning" is required and goes into the trace; be specific.
```

## Notes

- The replan-budget guard is critical — without it the reflector can loop forever blaming the planner for every executor failure.
- "done" with a partial answer (when replans are exhausted) is the right behavior — it's better than a runaway loop. Eval suites should include "should partial-answer" cases.
- Keep this Sonnet-class. Haiku reflectors under-trigger replans and over-trigger continues.
