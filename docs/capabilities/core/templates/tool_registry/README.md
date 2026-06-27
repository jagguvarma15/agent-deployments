# Tools

The scaffold emitted this tool subsystem (the **framework**); you implement the
**domain tools**.

- `schemas.py` — `ToolCall` / `ToolResult`, the model↔registry contract.
- `registry.py` — `Tool` + `ToolRegistry` (schema export + gated, retried dispatch).
- `permissions.py` — `Permission` tiers (ALWAYS / ASK / NEVER) + `PermissionGate`.
- `retry.py` — `run_with_retry` + `compact_error` (bounded retry, compacted errors).

## Register a tool

```python
from agent.tools import Permission, Tool, ToolRegistry

registry = ToolRegistry(approve=lambda call, reason: input(f"{reason}? [y/N] ") == "y")

registry.register(
    Tool(
        name="get_weather",
        description="Current weather for a city.",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        fn=lambda city: {"temp_c": 22, "city": city},
        permission=Permission.ALWAYS,
    )
)
```

## Use it in the agent loop

1. Hand `registry.schemas()` to your model as the tool list.
2. Parse the model's tool call into a `ToolCall`.
3. Run `registry.dispatch(call)` → a `ToolResult`, already **permission-gated** and
   **retry-wrapped**. Feed the `ToolResult.output` back to the model.

Tools default to `ASK` — a human approves each call via the `approve` callback —
unless you mark them `ALWAYS` (run silently) or `NEVER` (always refused). A tool
that raises is retried up to `max_attempts`; a persistent failure comes back as a
`ToolResult` with `.error` set and a compacted message, never an exception.
