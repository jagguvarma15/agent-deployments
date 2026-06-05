---
id: claude_agent_sdk_typescript
language: typescript
package: "@anthropic-ai/claude-agent-sdk"
versions:
  minimum: "^0.3.0"
  last_known_good: "0.3.163"
  notes: "0.3.x is the current line. API surface still evolving — pin tight and re-verify on every minor bump. Semver runs independently from the Python package."
---

# Framework: Claude Agent SDK (TypeScript)

**Language:** TypeScript
**Install:** `npm i @anthropic-ai/claude-agent-sdk` (last known good: `0.3.163`)

This is the TypeScript companion to the Python Claude Agent SDK. The two packages publish on independent semver tracks but expose a parallel API surface.

The full guide — agent loop, tools, MCP, subagents, hooks, anti-patterns — is in [`claude-agent-sdk.md`](claude-agent-sdk.md), with a dedicated **TypeScript variant** section that mirrors every Python example in TS. Read that doc; this file exists so the framework registry has a distinct id for the TypeScript variant.

See [`claude-agent-sdk.md#typescript-variant`](claude-agent-sdk.md#typescript-variant).
