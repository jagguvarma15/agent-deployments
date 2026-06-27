---
blueprints_version: 7420e28
applies_to:
  pattern: multi_agent
  primitives: [sub_agents, tool_use]
  modifiers: []
recommends:
  framework: crewai
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
  sandbox: null
  durable: null
  memory_store: null
  guardrail: null
  embedding: null
  rerank: null
local_only_swaps:
  - {from: stack/llm-claude, to: stack/llm-local-vllm}
est_tokens: 650
---

# Stack suggestion: Multi-Agent + Sub-agents + Tool Use

Multiple autonomous agents collaborating on a task — flat (peer-to-peer) or hierarchical (supervisor → workers). Fits ops investigations, complex research with parallel specialists, content production crews.

## Recommended picks (default mode)

| Slot | Pick | Why |
|---|---|---|
| Framework | `crewai` (Py) / `langgraph` (Py, for hierarchical) | CrewAI for role-based flat crews; LangGraph for explicit supervisor-worker graphs. |
| LLM | `stack/llm-claude` (Sonnet 4.6 for workers, Opus for supervisor when planning is heavy) | Workers handle bounded subtasks; supervisor synthesizes. |
| Relational | `relational.postgres` | Per-task state + per-role conversation history. |
| Cache | `cache.redis` | Inter-agent message passing (low-latency); rate limits. |
| Tracing | `obs.langfuse` | Per-agent trace bucketing; supervisor → worker spans nested. |
| Eval | `eval.promptfoo` | End-to-end task-completion cases. |

## Local-only swaps

- **`stack/llm-claude` → `stack/llm-local-vllm`** — for ops/research crews, 70B AWQ is workable. Hierarchical with Opus-class supervisor loses more quality than flat.

## See also

- [`docs/recipes/ops-crew.md`](../../recipes/ops-crew.md) (flat) — recipe shipping this combo
- [`docs/recipes/hierarchical-agent.md`](../../recipes/hierarchical-agent.md) (hierarchical) — recipe shipping this combo
- [`patterns/multi_agent/overview.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/patterns/multi_agent/overview.md)
- [`primitives/sub_agents/overview.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/primitives/sub_agents/overview.md)
