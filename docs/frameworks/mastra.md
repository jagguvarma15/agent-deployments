---
id: mastra
language: typescript
package: "@mastra/core"
versions:
  minimum: "^0.1.0"
  last_known_good: "0.1.0"
  notes: "Pre-1.0 line; the ^0.1.0 floor unlocks the agents + workflows + memory triad recipes assume, but the surface still moves between minors. Pin tight."
---

# Framework: Mastra

**Language:** TypeScript
**Install:** `npm install mastra @mastra/core`
**Version pinned:** ^0.1.0

## When to choose Mastra

Mastra is the right fit when a TypeScript track needs workflow orchestration, built-in memory, or multi-agent handoff out of the box. The framework is TS-native — Zod schemas, async/await, full type inference from agent to tool to result. Batteries-included is the central trade-off: memory, workflows, integrations, and tools live under one roof, so a single dependency unlocks most of the agent surface. The workflow engine carries directed-graph steps with branching and parallelism, similar to LangGraph but in TypeScript. The ecosystem is growing — active development, increasing community adoption — and the team's release cadence is fast.

Core abstractions:

- **Agent:** An LLM-powered entity with a system prompt, model config, and tools. Similar to Pydantic AI's Agent but in TypeScript.
- **Tool:** A typed function the agent can call. Defined with Zod schemas for input/output validation.
- **Workflow:** A directed graph of steps (like LangGraph but TS-native). Supports branching, looping, and parallel execution.
- **Memory:** Built-in memory primitives for conversation history and semantic memory. Integrates with vector stores.
- **Integration:** Pre-built connectors for external services (APIs, databases, SaaS tools).

## Minimal agent

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

## Tools

Tools attach to an `Agent` as a map of named entries. Each tool declares a Zod `parameters` schema, a `description`, and an `execute` async function. The framework hands the Zod schema to the model as the OpenAI-format tool definition; on invocation, the parsed arguments are validated and passed to `execute`. Tools can read `runtimeContext` for per-request state (DB connections, user identity) without globals.

## Structured output

Pass an `output` schema (Zod) to `agent.generate()` and Mastra binds the model's response to that shape, returning a typed result. The same shape works inside workflow steps via the step's `outputSchema`. Validation failures retry inside the framework's loop before surfacing.

## Memory

Memory is first-class. The `@mastra/memory` package provides short-term conversation buffers and long-term semantic memory (vector-store-backed). Wire on the `Agent` via the `memory:` option; the package ships adapters for the common vector stores (Pinecone, Qdrant, pgvector). For cross-session persistence, point the memory store at a durable backend; the contract is small enough to plug in a custom adapter.

## Streaming

`agent.stream()` returns an async iterable of partial response chunks (text and tool calls). Pair with Vercel AI SDK's React hooks for browser streaming, or with a Node HTTP framework's chunked response for server-only flows. Workflow steps can emit progress events that the caller subscribes to via the workflow run's emitter.

## Observability

Mastra emits OpenTelemetry spans for agent runs, tool calls, and workflow steps when the OTel SDK is initialized in-process — backends like Jaeger or Honeycomb pick them up automatically. The workflow engine also surfaces per-step status via the run's `events` channel for application-level monitoring.

## Anti-patterns

- **Plan & Execute** — Possible via workflows but no dedicated planner/reflector abstractions. If plan/execute is the central pattern, LangGraph (Python) is the better fit.
- **Complex state management with replay.** Workflows handle state but lack LangGraph's checkpointing depth (no replay, no branching history). For pause-and-resume across long-running workflows, that gap matters.
- **Mature production with deep ecosystem expectations.** Newer framework, smaller community, fewer production deployments compared to Vercel AI SDK or LangChain. Expect fewer pre-built integrations and shorter answer surfaces on StackOverflow / GitHub issues.
- **Heavier than Vercel AI SDK for simple agents.** More abstractions to learn. For a single-turn agent with one tool, Vercel AI SDK is lighter.
- **Integration lock-in risk.** Built-in integrations are convenient but may not match your exact needs. Custom backends require working against the framework's adapter shape, which can lag the underlying tool's native SDK.

## Composition matrix

- **ReAct** — Agent with tools runs a built-in reason-act-observe loop. Similar ergonomics to Pydantic AI.
- **Routing + Tool Use** — Agent with structured output for classification, separate agents per handler.
- **Prompt Chaining** — Workflow steps execute sequentially, passing typed data between stages.
- **Memory** — First-class memory support with built-in storage backends.
- **Multi-Agent** — Agent handoffs via workflows. Agents can delegate to other agents.

## Version notes

Pre-1.0 line; the `^0.1.0` floor unlocks the agents + workflows + memory triad recipes assume, but the surface still moves between minors. Pin tight.

| Version | Status | Notes |
|---------|--------|-------|
| `< 0.1.0` | Unsupported | Pre-stable agents API; workflow surface was experimental. No recipe expects this line. |
| `^0.1.0` | Recommended | Current pin in the frontmatter. The `Agent`, `Workflow`, and memory APIs are stable enough for greenfield TS work. |
| `0.2+` | Untested | Mastra publishes frequently; CI does not track. Treat any minor bump as a re-verify event against the canonical [`agent → tool → memory`] flow above. |

### Upgrade gotchas

- **Sub-package alignment.** `@mastra/core` ships independently from `@mastra/memory` and `@mastra/mcp`. Mixing minors across the sub-packages is the most common silent-break source — when you bump, bump them as a set.
- **Workflow step return shape.** Mid-0.1.x the step return type evolved to include `runtimeContext`. Steps that destructure only `inputData` will still work but pass-through context is the future-proof shape.
- **Memory backends.** The memory module's `Storage` adapter contract changed when the package split out. Recipes that wire a custom Postgres backend should follow the post-split adapter shape from the Mastra docs, not the inlined pre-split one.

### Why these bounds

The `^0.1.0` floor exists because that release cut over to the stable `Agent` + `Workflow` + `Memory` shape that any greenfield Mastra-based recipe would adopt. Pre-0.1 the agent surface was still moving fast enough that a pinned minor would break within weeks. No recorded upper bound — Mastra is pre-1.0 and the team is shipping fast — so the practical guidance is "pin the exact minor in `package.json`, bump deliberately, and re-test the `@mastra/memory` integration against the recipe before promoting."

## Used in this repo

| Prototype | Role |
|-----------|------|
| Not currently used | The TS track uses Vercel AI SDK. Mastra is documented as a TS framework option for teams that need workflow orchestration or built-in memory. |

Reference implementations:

- No direct recipes yet. See [frameworks/vercel-ai-sdk.md](vercel-ai-sdk.md) for the TS framework currently used in prototypes.
