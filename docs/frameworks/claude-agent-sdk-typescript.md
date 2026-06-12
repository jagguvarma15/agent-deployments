---
id: claude_agent_sdk_typescript
language: typescript
package: "@anthropic-ai/claude-agent-sdk"
versions:
  minimum: "^0.3.0"
  last_known_good: "0.3.163"
  notes: "0.3.x is the current line. API surface still evolving — pin tight and re-verify on every minor bump. Semver runs independently from the Python package."
tags: [typescript, claude-code-style, mcp-native, subagents]
when_to_load: "recipe.framework == 'claude_agent_sdk_typescript'"
---

# Framework: Claude Agent SDK (TypeScript)

**Language:** TypeScript
**Install:** `npm i @anthropic-ai/claude-agent-sdk` (last known good: `0.3.163`)

This is the TypeScript companion to the Python Claude Agent SDK. The two packages publish on independent semver tracks but expose a parallel API surface.

The full guide — agent loop, tools, MCP, subagents, hooks, anti-patterns — is in [`claude-agent-sdk.md`](claude-agent-sdk.md), with a dedicated **TypeScript variant** section that mirrors every Python example in TS. Read that doc; this file exists so the framework registry has a distinct id for the TypeScript variant.

See [`claude-agent-sdk.md#typescript-variant`](claude-agent-sdk.md#typescript-variant).

## MCP integration

The Claude Agent SDK (TypeScript) is MCP-native — MCP servers are configured at the query level and tools surface automatically during the session handshake.

**Streamable HTTP transport (the `mcp.tavily` capability):**

```ts
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Compare GraphQL vs gRPC for streaming workloads.",
  options: {
    mcpServers: {
      tavily: {
        type: "http",
        url: "https://mcp.tavily.com/mcp/",
        headers: { Authorization: `Bearer ${process.env.TAVILY_API_KEY}` },
      },
    },
    allowedTools: ["tavily_search", "tavily_extract"],
    systemPrompt: "You are a research assistant.",
  },
})) {
  if (message.type === "assistant") {
    console.log(message.message.content);
  }
}
```

**Stdio transport (subprocess-spawned servers):**

```ts
const options = {
  mcpServers: {
    postgres: {
      type: "stdio",
      command: "npx",
      args: ["-y", "@modelcontextprotocol/server-postgres", process.env.DATABASE_URL!],
    },
  },
  allowedTools: ["postgres_query"],
};
```

`allowedTools` gates tool exposure — the SDK only surfaces tools whose names appear there. Omitting it exposes every tool the server advertises.

## Version notes

See [`claude-agent-sdk.md#version-notes`](claude-agent-sdk.md#version-notes) — the canonical doc carries one table for the Python package and one for the TypeScript package side by side, since the two publish on independent semver tracks. `last_known_good: 0.3.163` for the TypeScript line.
