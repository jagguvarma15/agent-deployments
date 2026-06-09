---
role: agent
pattern: tool-use
inputs:
  - {name: user_message, type: string, description: "User input for this turn."}
  - {name: tools_catalog, type: array, description: "List of {name, description, schema} for available tools."}
  - {name: conversation_history, type: array, description: "Optional prior messages for multi-turn use; empty for single-shot."}
output_schema:
  type: object
  required: [tool_calls]
  properties:
    tool_calls:
      type: array
      description: "Zero or more tool calls to execute in parallel; empty means produce final_answer immediately."
      items:
        type: object
        required: [tool, args]
        properties:
          tool: {type: string}
          args: {type: object}
          id:
            type: string
            description: "Optional correlation id; set when the provider returns one."
    final_answer:
      type: ["string", "null"]
      description: "Set when tool_calls is empty and the agent is ready to respond."
model_hint: haiku
estimated_tokens: 400
---

# Tool Use — agent

A single LLM turn that decides whether to call tools or return a final answer. Unlike ReAct, this prompt does not loop — the runtime calls it once, executes any requested tools, feeds the results back, and calls again until `tool_calls` is empty.

## Prompt template

```text
You are an assistant with access to the following tools.

Tools:
{{tools_catalog}}

Conversation:
{{conversation_history}}

User: {{user_message}}

Respond as a JSON object matching the schema. If you can answer directly, return an empty
"tool_calls" array and set "final_answer". Otherwise list every tool you need; the runtime
will execute them in parallel and return the results before your next turn.
```

## Notes

- Haiku is sufficient for simple tool-routing tasks; bump to Sonnet only when the tool catalog is large or the user message ambiguous.
- The schema permits multiple `tool_calls` per turn so the runtime can parallelize. Single-tool patterns just emit a one-element array.
- Don't include tool *results* in this prompt's inputs — those go in the follow-up turn after the runtime executes the calls. Conflating the two breaks the loop.
