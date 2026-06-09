---
role: executor
pattern: plan-and-execute
inputs:
  - {name: step, type: object, description: "The Step to execute: {id, description, tool_hint, depends_on}."}
  - {name: available_tools, type: array, description: "Tools the executor may call."}
  - {name: prior_results, type: array, description: "ExecutionResults from upstream steps in depends_on."}
output_schema:
  type: object
  required: [step_id, success, output]
  properties:
    step_id:
      type: string
      description: "Echoes step.id for correlation in PlanExecuteState.execution_results."
    success:
      type: boolean
    output:
      type: string
      description: "Result summary; downstream steps and the reflector read this."
    error:
      type: ["string", "null"]
      description: "One-line failure summary when success is false."
    tool_calls:
      type: array
      description: "Tools the executor actually invoked; empty when the step was pure reasoning."
      items:
        type: object
        properties:
          tool: {type: string}
          args: {type: object}
model_hint: haiku
estimated_tokens: 500
---

# Plan & Execute — executor

Executes exactly one Step. Stateless across steps — each call sees only the current step, the tools, and the outputs of dependencies. Haiku-class because the planner has already done the hard reasoning.

## Prompt template

```text
You execute a single planned step. Stay within the step description.

Step:
- id: {{step.id}}
- description: {{step.description}}
- tool_hint: {{step.tool_hint}}

Available tools:
{{available_tools}}

Upstream results you may need:
{{prior_results}}

Respond as a JSON object matching the schema. Rules:
- Do exactly what the step description says — no more, no less. Don't expand scope.
- If the step requires a tool, call it via "tool_calls". If "tool_hint" is set, prefer
  it unless the upstream results suggest a better fit.
- On failure, set "success": false and put a one-line summary in "error". Don't retry —
  the reflector decides whether to replan.
```

## Notes

- Stateless-per-step is the discipline that lets Plan & Execute parallelize. Don't smuggle plan-wide context into the executor prompt — that's the planner's job.
- Haiku for execution + Sonnet for planning is the cost-optimal split. Bumping the executor to Sonnet rarely pays off.
- If a step consistently fails at execution, the bug is usually in the planner's decomposition (the step is underspecified), not the executor.
