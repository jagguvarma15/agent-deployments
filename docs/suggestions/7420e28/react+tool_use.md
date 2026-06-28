---
blueprints_version: 7420e28
applies_to:
  pattern: react
  primitives: [tool_use]
  modifiers: []
recommends:
  framework: pydantic_ai
  llm: stack/llm-claude
  api_layer: stack/api-fastapi
  relational: relational.postgres
  cache: cache.redis
  vector_db: null
  retrieval: null
  queue: null
  obs: obs.langfuse
  eval: eval.promptfoo
  mcp_servers: [mcp.tavily]
  sandbox: null
  durable: null
  memory_store: null
  guardrail: null
  embedding: null
  rerank: null
local_only_swaps:
  - {from: stack/llm-claude, to: stack/llm-local-vllm}
est_tokens: 600
---

# Stack suggestion: ReAct + Tool Use

Fits open-ended research-style agents — a single agent in a reason-act-observe loop with one or more external tools (web search, file fetch, lookups). Best when the steps to a successful answer aren't known in advance.

## Recommended picks (default mode)

| Slot | Pick | Why |
|---|---|---|
| Framework | `pydantic_ai` (Py) / `vercel_ai_sdk` (TS) | Tightest tool-decorator + native MCP client. Pydantic AI's `MCPServerStreamableHTTP` plugs into the agent's tool surface in one line. |
| LLM | `stack/llm-claude` (Sonnet 4.6) | Strong agentic reasoning at low cost-per-token. Haiku is too weak for multi-step loops. |
| Relational | `relational.postgres` | Stores per-session research history + cited sources. |
| Cache | `cache.redis` | Rate-limit backend; transient ReAct trace persistence between reasoning steps. |
| Tracing | `obs.langfuse` | Self-hosted; captures every LLM call + tool call in the loop. |
| Eval | `eval.promptfoo` | Pass-rate gates on golden questions; CI-friendly. |
| Tools | `mcp.tavily` | Tavily search exposed as an MCP tool the agent auto-discovers. |

## Local-only swaps

- **`stack/llm-claude` → `stack/llm-local-vllm`** — vLLM serving Llama 3.1 70B AWQ on a single A100 (or 8B on an L4). -5 to -15 quality points on agentic loops; trade for no API spend.

For Tavily, no fully-local alternative is wired yet — recipes that hard-require web search keep `mcp.tavily` even in `local_only` mode and gate on the API key.

## See also

- [`docs/recipes/research-assistant.md`](../../recipes/research-assistant.md) — the validated recipe shipping this combo
- [`patterns/react/overview.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/patterns/react/overview.md) — pattern overview
- [`docs/frameworks/pydantic-ai.md`](../../frameworks/pydantic-ai.md) `## MCP integration` — wiring code
