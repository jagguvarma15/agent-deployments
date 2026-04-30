# Framework: Mastra

**Language:** TypeScript
**Install:** `npm install mastra @mastra/core`
**Version pinned:** >=0.1.0

## Core abstractions

- **Agent:** An LLM-powered entity with a system prompt, model config, and tools. Similar to Pydantic AI's Agent but in TypeScript.
- **Tool:** A typed function the agent can call. Defined with Zod schemas for input/output validation.
- **Workflow:** A directed graph of steps (like LangGraph but TS-native). Supports branching, looping, and parallel execution.
- **Memory:** Built-in memory primitives for conversation history and semantic memory. Integrates with vector stores.
- **Integration:** Pre-built connectors for external services (APIs, databases, SaaS tools).

## Patterns it supports well

- **ReAct** — Agent with tools runs a built-in reason-act-observe loop. Similar ergonomics to Pydantic AI.
- **Routing + Tool Use** — Agent with structured output for classification, separate agents per handler.
- **Prompt Chaining** — Workflow steps execute sequentially, passing typed data between stages.
- **Memory** — First-class memory support with built-in storage backends.
- **Multi-Agent** — Agent handoffs via workflows. Agents can delegate to other agents.

## Patterns where it's awkward

- **Plan-and-Execute** — Possible via workflows but no dedicated planner/reflector abstractions.
- **Complex state management** — Workflows handle state but lack LangGraph's checkpointing depth (no replay, no branching history).

## Idiomatic minimal example

```typescript
import { Agent } from "@mastra/core";
import { anthropic } from "@ai-sdk/anthropic";
import { z } from "zod";

const agent = new Agent({
  name: "assistant",
  model: anthropic("claude-sonnet-4-6-20250514"),
  instructions: "You are a helpful assistant.",
  tools: {
    search: {
      description: "Search for information",
      parameters: z.object({ query: z.string() }),
      execute: async ({ query }) => `Results for: ${query}`,
    },
  },
});

const result = await agent.generate("What is MCP?");
console.log(result.text);
```

## Strengths

- **TS-native** — Built for TypeScript from the ground up. Zod schemas, async/await, full type inference.
- **Batteries included** — Memory, workflows, integrations, and tools in one framework.
- **Workflow engine** — Directed graph workflows with branching and parallelism, similar to LangGraph but in TS.
- **Growing ecosystem** — Active development, increasing community adoption.

## Trade-offs

- **Newer framework** — Smaller community, fewer production deployments compared to Vercel AI SDK or LangChain.
- **Heavier than Vercel AI SDK** — More abstractions to learn. For simple agents, Vercel AI SDK is lighter.
- **Integration lock-in** — Built-in integrations are convenient but may not match your exact needs.
- **Documentation gaps** — As a newer project, some advanced use cases lack documentation.

## Used in this repo

| Prototype | Role |
|-----------|------|
| Not currently used | The TS track uses Vercel AI SDK. Mastra is documented as a TS framework option for teams that need workflow orchestration or built-in memory. |

## Reference implementations

- No direct recipes yet. See [frameworks/vercel-ai-sdk.md](vercel-ai-sdk.md) for the TS framework currently used in prototypes.
