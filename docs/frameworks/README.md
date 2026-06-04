# Frameworks

Agent frameworks used in this repo. Each file answers: **"How do I implement the pattern?"**

| Framework | Language | Best for | Used in |
|-----------|----------|----------|---------|
| [LangGraph](langgraph.md) | Python | Stateful graphs, multi-step, multi-agent | research-assistant, code-review, memory, hierarchical |
| [Pydantic AI](pydantic-ai.md) | Python | Single agents, typed tools, simple ReAct | customer-support, docs-rag-qa, research-assistant |
| [CrewAI](crewai.md) | Python | Multi-agent crews | ops-crew |
| [Mastra](mastra.md) | TypeScript | Workflows, memory, multi-agent | Not yet used (documented as TS option) |
| [Vercel AI SDK](vercel-ai-sdk.md) | TypeScript | Lightweight agents, streaming | All TS tracks |

## How to pick a framework

**Python track:**
- Simple agent with tools → **Pydantic AI** (least boilerplate)
- Complex state, multi-step, checkpointing → **LangGraph** (best state management)
- Team of collaborating agents → **CrewAI** (purpose-built for crews)

**TypeScript track:**
- Most use cases → **Vercel AI SDK** (lightweight, production-proven)
- Need workflows, memory, or multi-agent → **Mastra** (batteries included)

## Frontmatter schema

Each framework doc carries a YAML frontmatter block declaring the canonical version pin so downstream consumers (e.g. `agent-scaffold`) read pins from one place instead of re-encoding them. Fields:

- `id` — the slug the scaffold REPL accepts (snake_case: `pydantic_ai`, `vercel_ai_sdk`, …). Maps to the PyPI / npm distribution via `package`.
- `language` — `python` or `typescript`.
- `package` — PyPI or npm distribution name.
- `versions.minimum` — current canonical pin (with operator, e.g. `">=0.1.0"`, `"^4.0.0"`, or exact `"0.3.21"`).
- `extra_packages` — optional list of companion deps the framework requires beyond the language baseline. Each entry: `{name, minimum}`.

Rationale and per-version notes (why a given floor / known-broken upper) are tracked separately. The body text's `**Version pinned:**` line mirrors `versions.minimum` for human readers.
