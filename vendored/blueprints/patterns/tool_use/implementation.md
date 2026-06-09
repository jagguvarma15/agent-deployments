# Tool Use — Implementation

## Core Interfaces

```
ToolSchema:
  name: string
  description: string
  parameters: JSONSchema                 // Describes expected arguments

ToolEntry:
  schema: ToolSchema
  handler: function(args) → any

ToolCallRequest:
  id: string                            // Unique call ID
  name: string
  arguments: object                     // Parsed arguments

ToolCallResult:
  tool_call_id: string
  content: string                       // Serialized result
```

## Core Pseudocode

### call_with_tools

```
function call_with_tools(messages, tool_entries):
  schemas = [entry.schema for entry in tool_entries]
  registry = {entry.schema.name: entry for entry in tool_entries}

  response = call_llm(messages: messages, tools: schemas)

  if not response.has_tool_calls:
    return {type: "text", content: response.text}

  results = []
  for tool_call in response.tool_calls:
    result = execute_tool_call(tool_call, registry)
    results.append(result)

  return {type: "tool_results", results: results, assistant_message: response}
```

### execute_tool_call

```
function execute_tool_call(tool_call, registry):
  // Check tool exists
  if tool_call.name not in registry:
    return {
      tool_call_id: tool_call.id,
      content: "Error: Unknown tool '" + tool_call.name + "'. " +
               "Available: " + join(registry.keys(), ", ")
    }

  entry = registry[tool_call.name]

  // Validate arguments
  errors = validate_json_schema(tool_call.arguments, entry.schema.parameters)
  if errors:
    return {
      tool_call_id: tool_call.id,
      content: "Error: Invalid arguments. " + format_errors(errors)
    }

  // Execute
  try:
    result = entry.handler(tool_call.arguments)
    return {
      tool_call_id: tool_call.id,
      content: serialize(result)
    }
  catch error:
    return {
      tool_call_id: tool_call.id,
      content: "Error: " + error.message
    }
```

### register_tool

```
function register_tool(registry, name, description, parameters, handler):
  registry[name] = {
    schema: {name: name, description: description, parameters: parameters},
    handler: handler
  }
```

## State Management

Tool Use is stateless per call — state is maintained by the caller (the agent loop or workflow). The registry is initialized once and remains constant during a session.

## Prompt Engineering Notes

### Tool Schema Design
- **Names:** Use verb_noun format: `search_web`, `read_file`, `calculate`
- **Descriptions:** Explain what the tool does and when to use it. Include examples.
- **Parameters:** Use descriptive parameter names. Include `description` for each parameter.
- **Required vs optional:** Mark only truly required parameters as required.

### Example Schema
```
{
  "name": "search_web",
  "description": "Search the web for information. Use when you need current data or facts you don't know.",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "The search query"},
      "max_results": {"type": "integer", "description": "Max results to return", "default": 5}
    },
    "required": ["query"]
  }
}
```

## Prompt Templates

These are production-ready templates. Copy and adapt — replace `{placeholders}` with your specifics.

### System prompt

```
You are {agent_role — e.g. "a data assistant", "a customer support agent"}.

You have access to tools. Use them when you need external data or to take actions.
Only call a tool when you genuinely need its output to answer the user.
Do not call tools to confirm information you already know.

After using a tool, incorporate the result into your response naturally.
When you have enough information, respond directly without calling any more tools.
```

### Tool schema template

```json
{
  "type": "function",
  "function": {
    "name": "{verb_noun — e.g. search_web, read_file, send_email}",
    "description": "{what_it_does}. Use when {when_to_use_it}. Do not use when {when_not_to_use_it}.",
    "parameters": {
      "type": "object",
      "properties": {
        "{param_name}": {
          "type": "{string|integer|boolean|array}",
          "description": "{what_this_parameter_is_and_what_values_are_valid}"
        }
      },
      "required": ["{required_param_names}"]
    }
  }
}
```

### Tool result injection (added to message history after tool call)

```
Tool result for {tool_name}:
{tool_output — truncated to {max_chars} characters if longer}
```

### Forced-finish injection (when max_rounds is approaching)

```
You have made {n} tool calls. Please synthesize what you have found so far and
provide your final response now, even if incomplete. Note any gaps in your answer.
```

### Customization guide

| Placeholder | What to put here |
|---|---|
| `{agent_role}` | A job title that frames how the LLM should reason about tool use |
| `"description"` in schema | The most important field. Include: what it does, when to use it, and when NOT to use it |
| `{tool_output}` | Truncate to the most relevant portion — raw output from a database or search API can be enormous |
| `{when_not_to_use_it}` | Explicitly listing exclusions in the description prevents misuse |

## Testing Strategy

- **Schema validation tests:** Valid args pass, invalid args produce clear errors
- **Dispatch tests:** Correct handler called for each tool name
- **Error handling tests:** Unknown tool, handler exception, timeout
- **Serialization tests:** Various return types serialize correctly

## Common Pitfalls

- **Vague tool descriptions:** LLM can't choose the right tool. Fix: be specific about when to use each tool.
- **Too many tools:** LLM struggles with 20+ tools. Fix: limit to 10–15 most relevant.
- **Missing error handling:** Tool crashes silently. Fix: always wrap handlers in try/catch.
- **Large results:** Tool returns huge output that fills context. Fix: truncate or summarize results.
