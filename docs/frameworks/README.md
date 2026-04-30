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
