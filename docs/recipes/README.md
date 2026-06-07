# Recipes

Full-spec agent blueprints showing how patterns, frameworks, and stack compose into real agents. Each file answers: **"Give me everything I need to build this agent."**

> **For tools that consume recipes programmatically:** the [top-level `catalog.yaml`](../../catalog.yaml) aggregates every recipe's frontmatter (plus capabilities, frameworks, and the agent-blueprints pattern catalog) into one machine-readable index. Don't parse this directory yourself — read the catalog. See [`MANIFEST_SCHEMA.md`](../../MANIFEST_SCHEMA.md). Editing a recipe? Run `uv run scripts/generate_catalog.py` and commit the regenerated `catalog.yaml` — the drift CI gate enforces this.

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
| [Restaurant Rebooking](restaurant-rebooking.md) | Event-Driven + Multi-Agent Flat | LangGraph / Mastra | Blueprint (design spec) |
| [Claude Code Subagent](claude-code-subagent.md) | ReAct + Routing/Tool use | Claude Agent SDK (Py / TS) | Blueprint (design spec) |

## Frontmatter

Every recipe opens with a YAML frontmatter block conformant to [`SCHEMA.md`](SCHEMA.md). That document is the canonical contract — every field, type, requiredness, and which `agent-scaffold` version consumes it. Open it before adding a new recipe or modifying an existing one.

Minimum required frontmatter:

```yaml
---
status: Blueprint (validated) | Blueprint (design spec)
languages: [python, typescript]
external_services: [...]         # v0.2.x consumer
capabilities: [...]              # v0.3+ consumer
---
```

See [`SCHEMA.md`](SCHEMA.md) for the full field set including `recipe_dependencies`, `required_files`, `bootstrap_config`, `topology`, and `roles`.

`claude_agent_sdk_python` and `claude_agent_sdk_typescript` are accepted `framework:` values; the per-language guide is at [`../frameworks/claude-agent-sdk.md`](../frameworks/claude-agent-sdk.md).
Accepted Python `framework:` values for new recipes: `pydantic_ai`, `langgraph`, `langchain`, `crewai`. TypeScript: `vercel_ai_sdk`, `mastra`. The full per-framework guide lives at [`../frameworks/README.md`](../frameworks/README.md).

## How to read a blueprint

Each blueprint follows a canonical section order:

1. **Composes** — links to the pattern, framework, stack, and cross-cutting docs. Opens with `## Composes` H2; the load list (files to feed an AI assistant) is the first H3 underneath.
2. **What it does** — problem statement and approach
3. **Architecture** — diagram of the agent's structure
4. **Data Models** — full Pydantic + Zod schemas
5. **API Contract** — every endpoint with request/response JSON
6. **Tool Specifications** — each tool with parameters and examples
7. **Prompt Specifications** — actual system prompts with design rationale
8. **Key files** — file-by-file implementation spec (Python + TypeScript)
9. **Implementation Roadmap** — ordered build steps
10. **Environment & Deployment** — env vars table, Docker reference
11. **Test Strategy** — example tests per tier
12. **Eval Dataset** — inline golden examples (required everywhere; design-spec gets 3–5 inline cases)
13. **Design Decisions** — trade-offs and rationale
14. **Reference Implementation** — full source code for validated blueprints; pseudocode-labeled for design-spec

Optional tail sections allowed where present (not required): `## Seed data`, `## Lifecycle`, `## Generation instructions`.

Multi-agent recipes use `role_kind` to declare each role's dispatcher / worker / supervisor / notifier classification. See [`SCHEMA.md`](SCHEMA.md#rolesrole_kind).
