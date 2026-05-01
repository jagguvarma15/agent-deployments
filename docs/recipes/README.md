# Recipes

Full-spec agent blueprints showing how patterns, frameworks, and stack compose into real agents. Each file answers: **"Give me everything I need to build this agent."**

## Validated (with reference implementation)

| Recipe | Pattern | Framework (Py / TS) | Status |
|--------|---------|---------------------|--------|
| [Customer Support Triage](customer-support-triage.md) | Routing + Tool Use | Pydantic AI / Vercel AI SDK | Blueprint (validated) |
| [Docs RAG QA](docs-rag-qa.md) | RAG | Pydantic AI / Vercel AI SDK | Blueprint (validated) |
| [Research Assistant](research-assistant.md) | ReAct | Pydantic AI / Vercel AI SDK | Blueprint (validated) |

## Design spec

| Recipe | Pattern | Framework (Py / TS) | Status |
|--------|---------|---------------------|--------|
| [Content Pipeline](content-pipeline.md) | Prompt Chaining | Pydantic AI / Vercel AI SDK | Blueprint (design spec) |
| [Code Review Agent](code-review-agent.md) | Plan-Execute-Reflect | LangGraph / Vercel AI SDK | Blueprint (design spec) |
| [Ops Crew](ops-crew.md) | Multi-Agent Flat | CrewAI / Vercel AI SDK | Blueprint (design spec) |
| [Parallel Enricher](parallel-enricher.md) | Parallel Calls | Pydantic AI / Vercel AI SDK | Blueprint (design spec) |
| [Memory Assistant](memory-assistant.md) | Memory | LangGraph / Vercel AI SDK | Blueprint (design spec) |
| [Hierarchical Agent](hierarchical-agent.md) | Multi-Agent Hierarchical | LangGraph / Vercel AI SDK | Blueprint (design spec) |

## How to read a blueprint

Each blueprint includes 13 sections:
1. **What it composes** — links to the pattern, framework, stack, and cross-cutting docs
2. **Architecture** — diagram of the agent's structure
3. **Data Models** — full Pydantic + Zod schemas
4. **API Contract** — every endpoint with request/response JSON
5. **Tool Specifications** — each tool with parameters and examples
6. **Prompt Specifications** — actual system prompts with design rationale
7. **Key files** — file-by-file implementation spec (Python + TypeScript)
8. **Implementation Roadmap** — ordered build steps
9. **Environment & Deployment** — env vars table, Docker reference
10. **Test Strategy** — example tests per tier
11. **Eval Dataset** — inline golden examples
12. **Design Decisions** — trade-offs and rationale
13. **Reference Implementation** — full source code (validated blueprints only)
