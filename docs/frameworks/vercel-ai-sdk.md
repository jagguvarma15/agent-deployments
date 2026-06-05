---
id: vercel_ai_sdk
language: typescript
package: ai
versions:
  minimum: "^4.0.0"
extra_packages:
  - {name: "@ai-sdk/anthropic", minimum: "^1.0.0"}
---

# Framework: Vercel AI SDK

**Language:** TypeScript
**Install:** `npm install ai @ai-sdk/anthropic`
**Version pinned:** ai ^4.0.0, @ai-sdk/anthropic ^1.0.0

## Core abstractions

- **`generateText()`:** Single LLM call that can use tools. The agent loops internally (up to `maxSteps`) calling tools until it produces a final text response.
- **`generateObject()`:** LLM call that returns structured output validated against a Zod schema. Ideal for classification, extraction, and structured data.
- **`streamText()` / `streamObject()`:** Streaming variants for real-time output.
- **`tool()`:** Defines a tool with a Zod schema and an execute function. Tools are passed to `generateText()` as a record.
- **Provider:** Model abstraction (`@ai-sdk/anthropic`, `@ai-sdk/openai`, etc.) that handles API communication.

## Patterns it supports well

- **ReAct** — `generateText()` with `tools` and `maxSteps` runs a built-in reason-act-observe loop. The simplest way to build an agent in TS.
- **Routing + Tool Use** — `generateObject()` for classification (structured output), `generateText()` per specialist. Clean and lightweight.
- **RAG** — Retrieval as a tool, generation via `generateText()`. Or inject retrieved context directly into the prompt.
- **Prompt Chaining** — Sequential `generateObject()` / `generateText()` calls. Each stage is a function call.
- **Parallel Calls** — `Promise.all()` with multiple `generateText()` calls. Standard TS async.

## Patterns where it's awkward

- **Plan-and-Execute** — No state management or checkpointing. You'd manage everything manually.
- **Multi-Agent (hierarchical)** — No supervisor abstraction. You'd orchestrate agent-calling-agent yourself.
- **Memory** — No built-in persistence. Conversation history must be managed externally.
- **Complex workflows** — No graph or workflow engine. For complex flows, consider Mastra or a manual state machine.

## Idiomatic minimal example

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

## Strengths

- **Minimal API surface** — Three functions (`generateText`, `generateObject`, `streamText`) cover most use cases. Easy to learn.
- **Type safety** — Zod schemas for tool inputs, structured outputs, and provider configs. Full TypeScript inference.
- **Streaming-first** — Built for real-time UIs. `streamText()` and `streamObject()` integrate with React Server Components and Next.js.
- **Provider-agnostic** — Swap models by changing the provider import. Same code works with Anthropic, OpenAI, Google, and more.
- **Lightweight** — No framework overhead. Functions, not classes. Composes with any TS codebase.
- **Production-proven** — Widely deployed via Vercel's ecosystem. Well-documented, actively maintained.

## Trade-offs

- **No orchestration** — No graph, no workflow, no state management. Complex multi-step agents require manual plumbing.
- **No multi-agent** — Each `generateText()` call is independent. No built-in agent-to-agent communication.
- **No memory** — Conversation history is your responsibility. Pass `messages` array manually.
- **UI-focused origin** — Some features (streaming, React hooks) are optimized for web UIs, which may be unnecessary for backend agents.

## Used in this repo

| Prototype | Role |
|-----------|------|
| `customer-support-triage` (TS) | Classifier with `generateObject()`, specialist with `generateText()` + tools |
| `docs-rag-qa` (TS) | RAG agent with retrieval tool |
| `research-assistant` (TS) | ReAct agent with web search tool |
| All TS prototypes | The standard TS framework for all prototypes in this repo |

## Reference implementations

- [recipes/customer-support-triage.md](../recipes/customer-support-triage.md) — Routing + Tool Use (TS track)
- [recipes/docs-rag-qa.md](../recipes/docs-rag-qa.md) — Agentic RAG (TS track)
- [recipes/research-assistant.md](../recipes/research-assistant.md) — ReAct agent (TS track)

## Version notes

One-line summary: the `^4.0.0` major rewrote `streamText` / `generateText` / `generateObject` and is the recipe-validated line; 3.x is incompatible, 5.x untested.

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
