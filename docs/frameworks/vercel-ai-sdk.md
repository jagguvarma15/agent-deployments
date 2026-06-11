---
id: vercel_ai_sdk
language: typescript
package: ai
versions:
  minimum: "^4.0.0"
  last_known_good: "4.0.0"
  notes: "The ^4.0.0 major rewrote `streamText` / `generateText` / `generateObject` and is the recipe-validated line; 3.x is incompatible, 5.x untested."
extra_packages:
  - {name: "@ai-sdk/anthropic", minimum: "^1.0.0"}
---

# Framework: Vercel AI SDK

**Language:** TypeScript
**Install:** `npm install ai @ai-sdk/anthropic`
**Version pinned:** ai ^4.0.0, @ai-sdk/anthropic ^1.0.0

## When to choose Vercel AI SDK

Vercel AI SDK is the right fit when a TypeScript track needs a small, function-shaped agent surface without orchestration overhead. The API is intentionally minimal — three functions (`generateText`, `generateObject`, `streamText`) cover most use cases. Type safety is end-to-end: Zod schemas for tool inputs, structured outputs, and provider configs with full TypeScript inference. Streaming is first-class: `streamText()` and `streamObject()` integrate with React Server Components and Next.js out of the box. Providers are swappable — change one import and the same code runs against Anthropic, OpenAI, Google, or others. The framework is lightweight (functions, not classes) and composes with any TypeScript codebase. Widely deployed via Vercel's ecosystem, well-documented, actively maintained.

Core abstractions:

- **`generateText()`:** Single LLM call that can use tools. The agent loops internally (up to `maxSteps`) calling tools until it produces a final text response.
- **`generateObject()`:** LLM call that returns structured output validated against a Zod schema. Ideal for classification, extraction, and structured data.
- **`streamText()` / `streamObject()`:** Streaming variants for real-time output.
- **`tool()`:** Defines a tool with a Zod schema and an execute function. Tools are passed to `generateText()` as a record.
- **Provider:** Model abstraction (`@ai-sdk/anthropic`, `@ai-sdk/openai`, etc.) that handles API communication.

## Minimal agent

```typescript
import { generateText, tool } from "ai";
import { anthropic } from "@ai-sdk/anthropic";
import { z } from "zod";

const result = await generateText({
  model: anthropic("claude-sonnet-4-6-20250514"),
  system: "You are a helpful assistant.",
  prompt: "What is MCP?",
  tools: {
    search: tool({
      description: "Search for information",
      parameters: z.object({ query: z.string() }),
      execute: async ({ query }) => `Results for: ${query}`,
    }),
  },
  maxSteps: 5,
});

console.log(result.text);
```

## Tools

Tools are values produced by the `tool()` helper. Each declares a Zod `parameters` schema, a `description`, and an `execute` async function. Pass tools to `generateText()` as a record keyed by tool name; `maxSteps` bounds how many tool-call rounds the model may take before terminating. The 4.x line emits typed `text-delta` / `tool-call` / `tool-result` stream parts, so a UI can reflect tool execution in real time.

## Structured output

`generateObject({ schema: z.object(...) })` binds the model's response to a Zod schema and returns a typed result on `.object`. Validation is strict on the 4.x line — partial matches that 3.x tolerated now fail and retry inside the loop. `streamObject()` provides the incremental version: the returned object materializes as the model emits, and each yield is fully typed.

## Memory

Vercel AI SDK does not ship a memory primitive. Conversation history is the caller's responsibility — pass a `messages` array on each `generateText()` invocation and persist it externally (Postgres, Redis, a session store). For typed message shapes, the SDK exports `CoreMessage` types that compose cleanly with whatever storage adapter the application uses. For semantic / long-term memory, the canonical pattern is a retrieval tool the agent calls; see [`../patterns/memory.md`](../patterns/memory.md) for the cross-framework shape.

## Streaming

Streaming is the framework's strongest surface. `streamText()` returns a `ReadableStream` of typed parts (`text-delta`, `tool-call`, `tool-result`, `finish`); `streamObject()` yields incremental Zod-validated partials. Both compose with React Server Components, Next.js route handlers, and standard Node response streams. The SDK ships React hooks (`useChat`, `useCompletion`) for browser-side wiring that handles the chunked transport automatically.

## Observability

OpenTelemetry support is built in — set `experimental_telemetry: { isEnabled: true }` on a call and the SDK emits spans for the LLM request and each tool invocation. Backends like Honeycomb, Tempo, or any OTel collector pick them up without further config. There's no first-class LangSmith-equivalent dashboard; OTel is the canonical path.

## Anti-patterns

- **Plan & Execute** — No state management or checkpointing. You'd manage everything manually; reach for LangGraph (Python) or Mastra (TypeScript) when the orchestration is load-bearing.
- **Multi-Agent (hierarchical).** No supervisor abstraction. You'd orchestrate agent-calling-agent yourself; CrewAI for Python, Mastra workflows for TypeScript.
- **Complex workflows.** No graph or workflow engine. For complex flows, consider Mastra or a manual state machine.
- **Cross-call memory built-in.** No built-in persistence. Conversation history must be managed externally.
- **Backend-only without UI considerations.** Some features (streaming, React hooks) are optimized for web UIs, which may be unnecessary for backend agents — the same code still works, but you carry the UI-adjacent surface area in your dependency tree.

## Composition matrix

- **ReAct** — `generateText()` with `tools` and `maxSteps` runs a built-in reason-act-observe loop. The simplest way to build an agent in TS.
- **Routing + Tool Use** — `generateObject()` for classification (structured output), `generateText()` per specialist. Clean and lightweight.
- **RAG** — Retrieval as a tool, generation via `generateText()`. Or inject retrieved context directly into the prompt.
- **Prompt Chaining** — Sequential `generateObject()` / `generateText()` calls. Each stage is a function call.
- **Parallel Calls** — `Promise.all()` with multiple `generateText()` calls. Standard TS async.

## MCP integration

The Vercel AI SDK provides `experimental_createMCPClient` for connecting to MCP servers and surfacing their tools to `generateText` / `streamText`.

**Streamable HTTP transport (the `mcp.tavily` capability):**

```ts
import { generateText, experimental_createMCPClient as createMCPClient } from "ai";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { anthropic } from "@ai-sdk/anthropic";

const tavily = await createMCPClient({
  transport: new StreamableHTTPClientTransport(
    new URL("https://mcp.tavily.com/mcp/"),
    { requestInit: { headers: { Authorization: `Bearer ${process.env.TAVILY_API_KEY}` } } }
  ),
});

const tools = await tavily.tools();

try {
  const result = await generateText({
    model: anthropic("claude-sonnet-4-6"),
    prompt: "Compare GraphQL vs gRPC for streaming workloads.",
    tools,
    maxSteps: 5,
  });
  console.log(result.text);
} finally {
  await tavily.close();
}
```

**Stdio transport (subprocess-spawned servers):**

```ts
import { Experimental_StdioMCPTransport } from "ai/mcp-stdio";

const local = await createMCPClient({
  transport: new Experimental_StdioMCPTransport({
    command: "npx",
    args: ["-y", "@modelcontextprotocol/server-postgres", process.env.DATABASE_URL!],
  }),
});
```

Tools returned by `client.tools()` are first-class AI SDK tools — they pass straight into `generateText` / `streamText` `tools:` without manual schema mapping.

## Version notes

The `^4.0.0` major rewrote `streamText` / `generateText` / `generateObject` and is the recipe-validated line; 3.x is incompatible, 5.x untested.

| Version | Status | Notes |
|---------|--------|-------|
| `< 4.0.0` | Known incompatible | The 3.x → 4.x rewrite changed the `streamText` / `generateText` / `generateObject` signatures. Recipes assume the 4.x shape; 3.x code will fail at type-check before runtime. |
| `^4.0.0` | Recommended | Current pin. Validated against [`../recipes/customer-support-triage.md`](../recipes/customer-support-triage.md), [`../recipes/docs-rag-qa.md`](../recipes/docs-rag-qa.md), [`../recipes/research-assistant.md`](../recipes/research-assistant.md). |
| `^5.0.0+` | Untested | CI does not validate. Re-verify the tool-call streaming shape and `generateObject` schema enforcement before adopting. |

### Upgrade gotchas

- **Provider-package alignment.** `@ai-sdk/anthropic ^1.0.0` is the matched Anthropic provider for SDK 4.x. Bumping `ai` without bumping `@ai-sdk/anthropic` in lockstep yields tool-result schema mismatches that surface as silent "model ignored the tool" behavior, not as type errors.
- **`generateObject` schema enforcement.** The 4.x line enforces the Zod schema strictly; 3.x silently fell through on partial matches. Recipes that depend on `output_strategy: 'object'` and assume "model will improvise" should re-test under 4.x.
- **`streamText` tool-call protocol.** The 4.x stream yields typed `text-delta` / `tool-call` / `tool-result` parts. UI code that pattern-matched on the older string-prefix protocol will break.

### Why these bounds

The `^4.0.0` floor exists because that major aligned the SDK's surface around the typed `generateObject` + `streamText` shape every TS-track recipe in this repo uses, and added strict Zod enforcement on structured output. Pre-4.x the API was less strict and the tool-call stream protocol was different enough that adapting was a rewrite, not a tweak. No recorded upper bound — pin to the 4.x major in `package.json` and re-verify the `customer-support-triage` triage flow when promoting to a new minor.

## Used in this repo

| Prototype | Role |
|-----------|------|
| `customer-support-triage` (TS) | Classifier with `generateObject()`, specialist with `generateText()` + tools |
| `docs-rag-qa` (TS) | RAG agent with retrieval tool |
| `research-assistant` (TS) | ReAct agent with web search tool |
| All TS prototypes | The standard TS framework for all prototypes in this repo |

Reference implementations:

- [recipes/customer-support-triage.md](../recipes/customer-support-triage.md) — Routing + Tool Use (TS track)
- [recipes/docs-rag-qa.md](../recipes/docs-rag-qa.md) — Agentic RAG (TS track)
- [recipes/research-assistant.md](../recipes/research-assistant.md) — ReAct agent (TS track)
