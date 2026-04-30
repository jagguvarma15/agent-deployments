# Recipes

Worked examples showing how patterns, frameworks, and stack compose into real agents. Each file answers: **"Show me a complete example."**

## Implemented (runnable code)

| Recipe | Pattern | Framework (Py / TS) | Status |
|--------|---------|---------------------|--------|
| [Customer Support Triage](customer-support-triage.md) | Routing + Tool Use | Pydantic AI / Vercel AI SDK | Implemented |
| [Docs RAG QA](docs-rag-qa.md) | RAG | Pydantic AI / Vercel AI SDK | Implemented |
| [Research Assistant](research-assistant.md) | ReAct | Pydantic AI / Vercel AI SDK | Implemented |

## Design intent (skeleton code)

| Recipe | Pattern | Framework (Py / TS) | Status |
|--------|---------|---------------------|--------|
| [Content Pipeline](content-pipeline.md) | Prompt Chaining | Pydantic AI / Vercel AI SDK | Skeleton |
| [Code Review Agent](code-review-agent.md) | Plan-Execute-Reflect | LangGraph / Vercel AI SDK | Skeleton |
| [Ops Crew](ops-crew.md) | Multi-Agent Flat | CrewAI / Vercel AI SDK | Skeleton |
| [Parallel Enricher](parallel-enricher.md) | Parallel Calls | Pydantic AI / Vercel AI SDK | Skeleton |
| [Memory Assistant](memory-assistant.md) | Memory | LangGraph / Vercel AI SDK | Skeleton |
| [Hierarchical Agent](hierarchical-agent.md) | Multi-Agent Hierarchical | LangGraph / Vercel AI SDK | Skeleton |

## How to read a recipe

Each recipe documents:
1. **What it composes** — links to the pattern, framework, stack, and cross-cutting docs
2. **Architecture** — diagram of the agent's structure
3. **Key files** — what's in the code and where
4. **How to run** — `docker compose up` or `make up`
5. **Example interaction** — request → response
6. **Design decisions** — why this pattern/framework/stack was chosen
