# Frameworks

Agent frameworks used in this repo. Each file answers: **"How do I implement the pattern?"**

| Framework | Language | Best for | Used in |
|-----------|----------|----------|---------|
| [LangGraph](langgraph.md) | Python | Stateful graphs, multi-step, multi-agent | research-assistant, code-review, memory, hierarchical |
| [LangChain](langchain.md) | Python | Tool-rich agents without a state graph; LCEL chains; ecosystem (retrievers, history backends) | Documented as Python option |
| [Pydantic AI](pydantic-ai.md) | Python | Single agents, typed tools, simple ReAct | customer-support, docs-rag-qa, research-assistant |
| [CrewAI](crewai.md) | Python | Multi-agent crews | ops-crew |
| [Claude Agent SDK](claude-agent-sdk.md) | Python | Claude Code-style subagent flows, MCP hosting, hook-gated tools | Documented as Python option |
| [Claude Agent SDK](claude-agent-sdk-typescript.md) | TypeScript | Claude Code-style subagent flows, MCP hosting, hook-gated tools | Documented as TypeScript option |
| [Mastra](mastra.md) | TypeScript | Workflows, memory, multi-agent | Not yet used (documented as TS option) |
| [Vercel AI SDK](vercel-ai-sdk.md) | TypeScript | Lightweight agents, streaming | All TS tracks |

For a full capability-by-capability comparison (tool use, structured output, memory, checkpointing, streaming, multi-agent, MCP, observability, …) across every framework above, see [`comparison.md`](comparison.md). The quick-pick decision tree below is the skim-friendly version; the matrix is the source of truth for the cell-by-cell ratings and links into each per-framework doc.

## How to pick a framework

**Python track:**
- Simple agent with tools → **Pydantic AI** (least boilerplate)
- Tool-rich agent, no state machine needed → **LangChain** (`AgentExecutor` + ecosystem)
- Complex state, multi-step, checkpointing → **LangGraph** (best state management)
- Team of collaborating agents → **CrewAI** (purpose-built for crews)
- Claude Code-style subagents, MCP hosting, hook-gated tool use → **Claude Agent SDK**

**TypeScript track:**
- Most use cases → **Vercel AI SDK** (lightweight, production-proven)
- Need workflows, memory, or multi-agent → **Mastra** (batteries included)
- Claude Code-style subagents, MCP hosting, hook-gated tool use → **Claude Agent SDK**

## Frontmatter schema

Each framework doc carries a YAML frontmatter block declaring the canonical version pin so downstream consumers (e.g. `agent-scaffold`) read pins from one place instead of re-encoding them. Fields:

- `id` — the slug the scaffold REPL accepts (snake_case: `pydantic_ai`, `vercel_ai_sdk`, …). Maps to the PyPI / npm distribution via `package`.
- `language` — `python` or `typescript`.
- `package` — PyPI or npm distribution name.
- `versions.minimum` — current canonical pin (with operator, e.g. `">=0.1.0"`, `"^4.0.0"`, or exact `"0.3.21"`).
- `extra_packages` — optional list of companion deps the framework requires beyond the language baseline. Each entry: `{name, minimum}`.

Rationale and per-version notes (why a given floor / known-broken upper) are tracked separately. The body text's `**Version pinned:**` line mirrors `versions.minimum` for human readers.
