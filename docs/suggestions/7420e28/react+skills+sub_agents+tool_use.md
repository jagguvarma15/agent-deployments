---
blueprints_version: 7420e28
applies_to:
  pattern: react
  primitives: [skills, sub_agents, tool_use]
  modifiers: []
recommends:
  framework: claude_agent_sdk_python
  llm: stack/llm-claude
  api_layer: stack/api-fastapi
  relational: relational.postgres
  cache: cache.redis
  vector_db: null
  retrieval: null
  queue: null
  obs: obs.langfuse
  eval: eval.promptfoo
  mcp_servers: []
  sandbox: sandbox.e2b
  durable: null
  memory_store: null
  guardrail: null
  embedding: null
  rerank: null
local_only_swaps: []
est_tokens: 700
---

# Stack suggestion: ReAct + Skills + Sub-agents + Tool Use

Claude-Code-style host that delegates delimited tasks to subagents, ships file-based skills the host loads on demand, and can execute code in a sandbox. Best for IDE-adjacent agents or developer-workflow assistants.

## Recommended picks (default mode)

| Slot | Pick | Why |
|---|---|---|
| Framework | `claude_agent_sdk_python` | Native subagent + skill support; MCP-native; matches Claude Code's session shape. |
| LLM | `stack/llm-claude` (Sonnet 4.6 for host + subagents) | Subagent dispatch + tool selection both benefit from Sonnet; Opus only if planning is heavy. |
| Relational | `relational.postgres` | Persists session, subagent dispatch logs. |
| Cache | `cache.redis` | Session cache; rate limits for tool calls. |
| Sandbox | `sandbox.e2b` | Code-execution surface for any "run this script" subagent step. |
| Tracing | `obs.langfuse` | Captures subagent dispatch as nested traces. |
| Eval | `eval.promptfoo` | Skill-loading regression cases. |

## Local-only swaps

No fully-local mode wired yet. The Claude Agent SDK is Anthropic-bound; a `local_only` variant would require swapping the SDK for a different framework (the recipe currently doesn't support that swap).

## See also

- [`docs/recipes/claude-code-subagent.md`](../../recipes/claude-code-subagent.md) — the recipe shipping this combo
- [`primitives/sub_agents/overview.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/primitives/sub_agents/overview.md), [`primitives/skills/overview.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/primitives/skills/overview.md)
- [`docs/frameworks/claude-agent-sdk.md`](../../frameworks/claude-agent-sdk.md) `## MCP integration` — subagent + MCP wiring
