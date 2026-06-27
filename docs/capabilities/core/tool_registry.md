---
id: core.tool_registry
kind: core
layer: agent
provides: [tool_registry, tool_permissions, compact_error_retry]
env_vars: []
docker: null
probe: null
bootstrap_step: null
provisioning_time: instant
cost_tier: free
card:
  name: Tool registry
  description: "Typed tool registry with Always/Ask/Never permission tiers and compact-error retry — the T1 tool-agent substrate."
  capabilities_provided: [tool_registry, tool_permissions, compact_error_retry]
  required_credentials: []
emit_files:
  - source: templates/tool_registry/**
    dest: agent/tools/
deploy_configs: []
docs: |
  Emits the agent/tools/ package: a typed Tool registry (JSON-Schema export +
  dispatch), Always/Ask/Never permission gating with a human-approval seam, and
  a compact-error bounded-retry wrapper. The generated agent registers its
  domain tools against this registry; the scaffold emits the framework, not the
  domain tool functions.
tags: [core, tool-use, permissions, retry]
when_to_load: "recipe tier is T1 or higher (the tier preset seeds core.tool_registry)"
---

# Core: Tool registry

The tool-agent substrate emitted at the **T1** tier. It ships the framework a
tool-using agent needs — a typed registry, permission tiers, and a retry
wrapper — and leaves the domain tool functions for the recipe/model to fill in.

## Emitted files

`emit_files` copies `templates/tool_registry/**` into the project's `agent/tools/`
package:

| File | Role |
|---|---|
| `schemas.py` | `ToolCall` / `ToolResult` — the model↔registry contract (Pydantic). |
| `registry.py` | `Tool` + `ToolRegistry` — schema export and permission-gated, retry-wrapped dispatch. |
| `permissions.py` | `Permission` (ALWAYS / ASK / NEVER) + `PermissionGate` — the tool-permission boundary, with a human-approval callback for ASK. |
| `retry.py` | `run_with_retry` + `compact_error` — bounded retry that returns a clean `ToolResult` instead of raising or spinning. |
| `__init__.py` | Re-exports the public surface (`from agent.tools import Tool, ToolRegistry, Permission, ...`). |
| `README.md` | How to register a domain tool and drive the dispatch loop. |

The copier never overwrites a file the model emitted at the same path, so a
recipe can specialize any of these while inheriting the rest.

## Wiring

The agent hands `registry.schemas()` to the model, parses the returned tool call
into a `ToolCall`, and calls `registry.dispatch(call)` — which gates the call by
its permission tier and runs it through the retry wrapper, returning a
`ToolResult`. Tools default to `ASK` (a human approves each call); mark a tool
`ALWAYS` to run it silently or `NEVER` to refuse it.

## See also

- Reference implementation: the `tool_use` primitive in agent-blueprints
  (`primitives/tool_use/code/python/{tool_use,permissions,retry}.py`).
