---
role: agent
pattern: react
inputs:
  - {name: question, type: string, description: "User-supplied task driving the loop."}
  - {name: tools_catalog, type: array, description: "List of {name, description, schema} for every tool the agent may call."}
  - {name: prior_steps, type: array, description: "Previously executed ReActStep entries (thought/action/observation)."}
output_schema:
  type: object
  required: [thought]
  properties:
    thought:
      type: string
      description: "Reasoning step justifying the next action or final answer."
    action:
      type: ["object", "null"]
      description: "Tool call to execute next; null when terminating with final_answer."
      properties:
        tool: {type: string}
        args: {type: object}
      required: [tool]
    final_answer:
      type: ["string", "null"]
      description: "Set when the agent decides it has enough information; omits action."
model_hint: sonnet
estimated_tokens: 600
---

# ReAct — agent

One iteration of the reason → act → observe loop. The agent reads the question, the catalog of tools, and every prior step, then emits exactly one of (a) a thought + action, or (b) a thought + final_answer.

## Prompt template

```text
You are an agent that uses tools to answer questions. Reason in one step, then either
call exactly one tool or produce a final answer — never both.

Available tools:
{{tools_catalog}}

Conversation so far:
{{prior_steps}}

Question:
{{question}}

Respond as a JSON object matching the schema. Set "final_answer" only when the prior
observations are sufficient. Otherwise set "action" with a tool name from the catalog.
```

## Notes

- `thought` is required on every turn so the trace is debuggable even when the agent terminates immediately.
- `action` and `final_answer` are mutually exclusive — enforce that in code, not the prompt. The schema permits either to be null but downstream code must reject both being present.
- Keep `prior_steps` compact (drop tool argument bodies past N tokens) before injecting; otherwise the loop's input grows quadratically with iterations.
