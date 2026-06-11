---
id: claude_agent_sdk_python
language: python
package: claude-agent-sdk
versions:
  minimum: "0.2.0"
  last_known_good: "0.2.90"
  notes: "0.2.x is the current line. API surface still evolving — pin tight and re-verify on every minor bump."
extra_packages:
  - {name: anthropic, minimum: "0.69.0"}
---

# Framework: Claude Agent SDK

**Languages:** Python (`claude-agent-sdk`) and TypeScript (`@anthropic-ai/claude-agent-sdk`)
**Install:**
- Python: `uv add claude-agent-sdk` (last known good: `0.2.90`)
- TypeScript: `npm i @anthropic-ai/claude-agent-sdk` (last known good: `0.3.163`)

The Claude Agent SDK is Anthropic's first-party harness for building Claude Code-style agents: a tool-use loop, structured tool definitions, MCP server hosting and consumption, subagent invocation, and the same lifecycle hooks (PreToolUse / PostToolUse / Stop) that Claude Code itself exposes. Reach for it when you want a Claude-Code-shaped agent in your own process rather than a thin wrapper around `anthropic.Anthropic().messages.create()`.

The two language packages mirror each other. They publish on separate semver tracks (Python is on `0.2.x`, TypeScript is on `0.3.x` as of mid-2026) but the surface is parallel: query, tools, MCP, subagents, hooks.

## When to choose the Agent SDK

| You need | Pick |
|----------|------|
| Claude Code-style agent (subagents, MCP, hooks) in your own process | **Claude Agent SDK** |
| One-shot completion or single structured-output call | [`anthropic` SDK](../stack/llm-claude.md) — the agent loop is overkill |
| Tool-use loop with a Python ecosystem (retrievers, history backends) | LangChain |
| Stateful multi-step graph, checkpointing, multi-agent supervisor | [LangGraph](langgraph.md) |
| Typed single-agent with `result_type` | [Pydantic AI](pydantic-ai.md) |
| Lightweight TypeScript agent, especially in serverless | [Vercel AI SDK](vercel-ai-sdk.md) |

Picking heuristic: if you'd describe what you're building as "a Claude Code subagent that runs outside Claude Code" or "an MCP server that exposes my tools to any Claude client", the Agent SDK is the lowest-friction path. If you'd describe it as "a chatbot that calls one tool", the raw Anthropic SDK is fewer moving parts.

## Mental model

- **Agent loop** — the SDK drives a request → tool-call → tool-result → request cycle until the model emits a final text block or hits a stop condition. You provide the system prompt and tool list; the SDK owns the loop.
- **Tools** — typed Python functions (or async functions) with a JSON Schema. The SDK marshals the model's tool call into your function and the return into the next request.
- **MCP servers** — both *consumed* (the SDK passes through external MCP server configs the same way Claude Code does) and *hosted* (your process can expose its tools as an MCP server for other Claude clients to call).
- **Subagents** — separate Claude sessions invoked from a parent agent via the `Agent` tool. Each subagent has its own system prompt, tool set, and context window. Use them to isolate work that would otherwise pollute the parent's history.
- **Hooks** — synchronous callbacks before / after each tool use and on session stop. Used for audit logging, permission gates, and observability.
- **Session resumption** — the SDK can serialize and resume a session, so long-running agents survive process restarts.

For the canonical API surface, defer to the [Claude Agent SDK documentation](https://docs.anthropic.com/en/api/agent-sdk-overview) — the contract below mirrors what's there but the SDK is the source of truth.

## Minimal Python agent

A complete single-tool agent, ~40 lines:

```python
"""Minimal Claude Agent SDK agent — one tool, one query.

Run:
    ANTHROPIC_API_KEY=... uv run --with 'claude-agent-sdk>=0.2,<0.3' python agent.py
"""
from __future__ import annotations

import anyio
from datetime import datetime, timezone

from claude_agent_sdk import ClaudeAgentOptions, query, tool


@tool(
    "get_time",
    "Return the current UTC time as an ISO-8601 string.",
    {"type": "object", "properties": {}, "required": []},
)
async def get_time(_args: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {"content": [{"type": "text", "text": now}]}


async def main() -> None:
    options = ClaudeAgentOptions(
        system_prompt="You are a concise time assistant. Always call get_time before answering.",
        tools=[get_time],
        max_turns=4,
    )
    async for message in query(prompt="What time is it now?", options=options):
        # Stream the assistant text blocks as they arrive.
        for block in getattr(message, "content", []):
            if getattr(block, "type", None) == "text":
                print(block.text, end="", flush=True)
    print()


if __name__ == "__main__":
    anyio.run(main)
```

Notes:

- `query()` is an async generator that yields messages as the model produces them. The shape of each message mirrors the Anthropic API content-block protocol — assistant text blocks, tool-use blocks, and tool-result blocks.
- `max_turns` is the loop cap. Without it, a confused model can grind through the context window calling the same tool. Set it.
- `system_prompt` is the agent's persona + instructions. The SDK does not auto-inject anything; whatever you don't put here, the model doesn't know.

## Tools

```python
from claude_agent_sdk import tool


@tool(
    "lookup_user",
    "Fetch a user record by id. Use when the user mentions an id or email.",
    {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "Internal user id, e.g. 'usr_1234'",
            },
            "fields": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Subset of profile fields to return.",
                "default": [],
            },
        },
        "required": ["user_id"],
    },
)
async def lookup_user(args: dict) -> dict:
    user_id = args["user_id"]
    fields = args.get("fields", [])
    try:
        record = await fetch_user(user_id, fields)
    except UserNotFound as exc:
        # Return an error block instead of raising; the model can recover.
        return {
            "content": [{"type": "text", "text": f"User {user_id!r} not found: {exc}"}],
            "is_error": True,
        }
    return {"content": [{"type": "text", "text": str(record)}]}
```

Conventions:

- The third `@tool` argument is the **input JSON Schema**. The model sees only this — descriptions matter for tool selection.
- Return shape is the Anthropic tool-result content-block list: `{"content": [{"type": "text", "text": "..."}], "is_error": False}`. Set `"is_error": True` for recoverable failures; raise only for bugs.
- Async tools are first-class. The SDK awaits them inside its event loop — don't mix sync `time.sleep` into an async tool path.
- Tools that hit a remote system must own their own timeout. `max_turns` is a loop cap, not a wall clock per tool.

## MCP server hosting and consumption

Consuming an external MCP server (the same shape Claude Code uses):

```python
from claude_agent_sdk import ClaudeAgentOptions, query


options = ClaudeAgentOptions(
    system_prompt="You read files via the filesystem MCP server.",
    mcp_servers=[
        {
            "name": "fs",
            "command": "uvx",
            "args": ["mcp-server-filesystem", "--root", "/tmp/sandbox"],
        }
    ],
    allowed_tools=["fs:read_file", "fs:list_directory"],
    max_turns=6,
)
```

Hosting your own tools as an MCP server (so other Claude clients — Claude Code, Claude Desktop, another Agent SDK process — can invoke them) is the inverse path: define tools with the same `@tool` decorator, then run an MCP server entry point that exposes them. The SDK ships a server helper; the wire protocol is the same MCP spec covered in [`../stack/tool-protocol-mcp.md`](../stack/tool-protocol-mcp.md). For the protocol reference and a worked client implementation, see that doc.

The split is intentional: the Agent SDK is one consumer / host of the MCP protocol, not its definition.

## Subagents

A subagent is a fully separate Claude session, invoked from the parent agent via the SDK's `Agent` tool. It has its own system prompt, tool list, and context window — and crucially, its turn history does not pollute the parent's history. Use them when:

- A sub-task is independently scoped (research a topic, run a code review pass) and the parent only needs the result.
- The parent's context window is being eaten by the sub-task's verbose tool outputs.
- The sub-task needs a different model tier (use Haiku for grep-y work, Sonnet for the parent reasoning).

Define a subagent as a markdown file under `.claude/agents/<name>.md`:

```markdown
---
name: code-reviewer
description: Reviews a diff for security and correctness regressions.
tools: [Read, Grep, Bash]
model: sonnet
---

You review code changes for security regressions and obvious correctness bugs.
Output a structured list: severity, file:line, issue, suggested fix.
```

The parent agent invokes it via the standard `Agent` tool:

```python
options = ClaudeAgentOptions(
    system_prompt="You orchestrate code review. Delegate detail work to code-reviewer.",
    subagents_dir=".claude/agents",
    max_turns=8,
)
```

The companion recipe in [`../recipes/`](../recipes/) (claude-code-subagent) walks through the full pattern.

## Hooks

Three hook surfaces. All are synchronous: they run on the SDK's event loop, can mutate the action, and can refuse it.

```python
from claude_agent_sdk import ClaudeAgentOptions, HookContext


async def pre_tool_use(ctx: HookContext) -> dict | None:
    """Audit-log every tool call; refuse writes outside an allowlist."""
    tool_name = ctx.tool_name
    args = ctx.tool_input
    if tool_name == "write_file":
        path = args.get("path", "")
        if not path.startswith("/tmp/sandbox/"):
            return {"deny": True, "reason": f"write to {path!r} is outside the sandbox"}
    await audit_log({"event": "tool_use", "tool": tool_name, "args": args})
    return None  # allow


async def post_tool_use(ctx: HookContext) -> None:
    await audit_log({"event": "tool_result", "tool": ctx.tool_name, "ok": not ctx.is_error})


async def on_stop(ctx: HookContext) -> None:
    await audit_log({"event": "session_stop", "turn_count": ctx.turn_count})


options = ClaudeAgentOptions(
    system_prompt="...",
    tools=[...],
    hooks={
        "PreToolUse": pre_tool_use,
        "PostToolUse": post_tool_use,
        "Stop": on_stop,
    },
)
```

Security implications worth pinning:

- **PreToolUse is the permission gate.** Any tool that mutates the world (file writes, network POSTs, shell exec) should be gated by a deny-by-default allowlist check here. A leaky pre-hook is the SDK equivalent of an SSRF.
- **Hooks see redacted inputs.** If a tool argument contains a credential (`{"token": "..."}`), the audit log captures it. Strip secrets in the hook or scope your logger to a sealed sink.
- **Hooks can stall the loop.** A 5-second `await` inside `PreToolUse` adds 5 seconds to every tool call. Keep hooks cheap; offload to a queue for anything slow.

## TypeScript variant

The npm package is `@anthropic-ai/claude-agent-sdk`. API parity with the Python package; semver is independent.

```typescript
// agent.ts
// Run:
//   ANTHROPIC_API_KEY=... npx tsx agent.ts
import { query, tool, type ClaudeAgentOptions } from "@anthropic-ai/claude-agent-sdk";

const getTime = tool(
  "get_time",
  "Return the current UTC time as an ISO-8601 string.",
  { type: "object", properties: {}, required: [] },
  async (_args) => ({
    content: [{ type: "text", text: new Date().toISOString() }],
  }),
);

const options: ClaudeAgentOptions = {
  systemPrompt: "You are a concise time assistant. Always call get_time before answering.",
  tools: [getTime],
  maxTurns: 4,
};

for await (const message of query({ prompt: "What time is it now?", options })) {
  for (const block of message.content ?? []) {
    if (block.type === "text") process.stdout.write(block.text);
  }
}
process.stdout.write("\n");
```

Tools, MCP, subagents, and hooks all mirror the Python surface:

```typescript
import { tool, type HookContext } from "@anthropic-ai/claude-agent-sdk";

const lookupUser = tool(
  "lookup_user",
  "Fetch a user record by id.",
  {
    type: "object",
    properties: {
      user_id: { type: "string", description: "Internal user id, e.g. 'usr_1234'" },
      fields: { type: "array", items: { type: "string" }, default: [] },
    },
    required: ["user_id"],
  },
  async ({ user_id, fields }) => {
    try {
      const record = await fetchUser(user_id, fields);
      return { content: [{ type: "text", text: JSON.stringify(record) }] };
    } catch (e) {
      return { content: [{ type: "text", text: `User ${user_id} not found` }], is_error: true };
    }
  },
);

const preToolUse = async (ctx: HookContext): Promise<{ deny: true; reason: string } | null> => {
  if (ctx.toolName === "write_file" && !ctx.toolInput.path?.startsWith("/tmp/sandbox/")) {
    return { deny: true, reason: `write to ${ctx.toolInput.path} is outside the sandbox` };
  }
  return null;
};
```

Subagents in TypeScript follow the same `.claude/agents/<name>.md` convention; pass `subagentsDir: ".claude/agents"` in `ClaudeAgentOptions`. The Python conventions section above is authoritative for the markdown frontmatter shape.

The companion TS framework id for SR1b is `claude_agent_sdk_typescript`; see [`claude-agent-sdk-typescript.md`](claude-agent-sdk-typescript.md) for the standalone frontmatter (it points back to this doc).

## Composition with patterns

| Pattern | Fit | Notes |
|---------|-----|-------|
| [ReAct](../patterns/react.md) | **Fits** — this is the SDK's default loop | `query()` + tools, done |
| [Routing / tool use](../patterns/routing-tool-use.md) | **Fits** | Single agent with a routing tool, or pre-hook intent gate |
| [RAG](../patterns/rag.md) | Awkward — overkill for one retrieval call | Use raw `anthropic` SDK + retriever |
| [Prompt chaining](../patterns/prompt-chaining.md) | Awkward — no chain primitive | Use LangChain LCEL or raw SDK |
| [Parallel calls](../patterns/parallel-calls.md) | Awkward — agent loop is sequential | `asyncio.gather` over raw SDK calls |
| [Plan-execute-reflect](../patterns/plan-execute-reflect.md) | Borderline — works via subagents | `LangGraph` is more idiomatic |
| [Multi-agent (flat)](../patterns/multi-agent-flat.md) | **Fits via subagents** | Each peer is a subagent; parent coordinates |
| [Multi-agent (hierarchical)](../patterns/multi-agent-hierarchical.md) | **Fits via subagents** | Subagent invocation is the supervisor primitive |
| [Event-driven](../patterns/event-driven.md) | Awkward — SDK is request/response | Wrap the SDK call in your own consumer loop, or use LangGraph |
| [Memory](../patterns/memory.md) | Fits via session resumption | Long-conversation memory layered separately (see [`../cross-cutting/observability.md`](../cross-cutting/observability.md) for cross-session trace correlation) |

Use the SDK when your mental model is "Claude Code, but mine". Reach past it (LangGraph, LangChain, raw SDK) when the abstraction stops matching the work shape.

## Anti-patterns

- **Using the SDK for a one-shot completion.** The agent loop, tool registry, and hook plumbing exist to be used. For "summarize this email", call `anthropic.Anthropic().messages.create()` directly — see [`../stack/llm-claude.md`](../stack/llm-claude.md).
- **Building multi-agent orchestration directly with tool-from-tool calls.** Use [LangGraph](langgraph.md) (Python) or [Mastra](mastra.md) (TypeScript) — both have purpose-built supervisor primitives. Subagents work for tree-shaped delegation; they don't model fan-out / fan-in cleanly.
- **Skipping `max_turns`.** A confused model loops the same tool until it eats the context window. Set it.
- **Returning raw Python objects from tools.** Tools must return the Anthropic content-block shape (`{"content": [...], "is_error": False}`). Anything else is coerced and the model sees gibberish.
- **Leaking secrets through PostToolUse hooks.** The hook sees the full tool result. If a tool returns a token (`{"token": "..."}`), unscoped audit logging captures it. Redact or sink to a sealed log.
- **Using PreToolUse for slow remote checks.** A 5-second check stalls every tool call. Cache the decision or move to an out-of-loop policy engine.
- **Mixing the SDK's `anthropic` extra-package version with a hand-pinned one.** The SDK pins its own floor internally; let it. Pinning `anthropic` separately to a lower version causes `tool_use` content-block schema mismatches.

## Observability

Hooks are the canonical observability seam. The pattern: emit a structured event on each tool boundary; aggregate at the audit-log layer.

```python
import json
from claude_agent_sdk import HookContext


async def pre_tool_use(ctx: HookContext) -> None:
    print(json.dumps({
        "event": "tool_use_start",
        "session_id": ctx.session_id,
        "tool": ctx.tool_name,
        "input_preview": str(ctx.tool_input)[:200],
    }))


async def post_tool_use(ctx: HookContext) -> None:
    print(json.dumps({
        "event": "tool_use_end",
        "session_id": ctx.session_id,
        "tool": ctx.tool_name,
        "is_error": ctx.is_error,
        "latency_ms": ctx.elapsed_ms,
    }))
```

OpenTelemetry — start an OTel span in PreToolUse, end it in PostToolUse, link by `session_id`. The exporter side is identical to any other OTel-instrumented service; see [`../stack/opentelemetry.md`](../stack/opentelemetry.md) for the canonical setup. For correlated cross-session traces (parent invokes subagent), propagate the trace context through the subagent invocation as a tool argument or via a baggage header.

For self-hosted trace UI, see [`../stack/tracing-langfuse.md`](../stack/tracing-langfuse.md); the hook payload shape above drops into Langfuse's generic event ingestion.

## MCP integration

The Claude Agent SDK is MCP-native — MCP servers are configured at the harness level and tools surface to the agent automatically. There is no separate "discover tools" step in user code; the SDK handles discovery during the session handshake.

**Streamable HTTP transport (the `mcp.tavily` capability):**

```python
import os
from claude_agent_sdk import ClaudeAgentClient, ClaudeAgentOptions, McpServerConfig

options = ClaudeAgentOptions(
    mcp_servers={
        "tavily": McpServerConfig(
            type="http",
            url="https://mcp.tavily.com/mcp/",
            headers={"Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}"},
        ),
    },
    allowed_tools=["tavily_search", "tavily_extract"],
    system_prompt="You are a research assistant.",
)

async with ClaudeAgentClient(options=options) as client:
    response = await client.query("Compare GraphQL vs gRPC for streaming workloads.")
    print(response.text)
```

**Stdio transport (subprocess-spawned servers):**

```python
options = ClaudeAgentOptions(
    mcp_servers={
        "postgres": McpServerConfig(
            type="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-postgres", os.environ["DATABASE_URL"]],
        ),
    },
    allowed_tools=["postgres_query"],
)
```

`allowed_tools` is the gate — the SDK only exposes tools whose names appear there. Omitting `allowed_tools` exposes every tool the server advertises (use cautiously).

## Version notes

One-line summary: API surface still evolving on both language tracks; pin tight and re-verify on every minor bump. (Matches frontmatter `versions.notes` on both files.)

The Python (`claude-agent-sdk`) and TypeScript (`@anthropic-ai/claude-agent-sdk`) packages publish on independent semver tracks. Read each table for the language you ship.

**Python** — `claude-agent-sdk`:

| Version | Status | Notes |
|---------|--------|-------|
| `< 0.2.0` | Unsupported | The 0.1.x line had a different `ClaudeAgentOptions` field set and a different hook context shape. Recipes targeting the 0.2.x surface won't import. |
| `0.2.0 – 0.2.90` | Recommended | Current pin range. `last_known_good: "0.2.90"` per frontmatter. Validated against the [minimal Python agent](#minimal-python-agent) and the [hooks](#hooks) examples in this doc. |
| `0.2.91+` | Untested | Likely fine — 0.2.x has held additive — but CI does not validate. Re-verify the [tools](#tools) content-block shape before adopting. |
| `>=0.3.0` | Likely incompatible | The SDK team has shipped minor-line breakages in past majors; treat 0.3 as a re-port rather than a bump. |

**TypeScript** — `@anthropic-ai/claude-agent-sdk`:

| Version | Status | Notes |
|---------|--------|-------|
| `< 0.3.0` | Unsupported | The 0.2.x line had a different `ClaudeAgentOptions` field shape (camelCase variants drifted) and a different `tool()` return type. |
| `^0.3.0` (last known good `0.3.163`) | Recommended | Current pin. Validated against the [TypeScript variant](#typescript-variant) section in this doc. |
| `>=0.4.0` | Untested | npm publishes are frequent; pin to the 0.3 major and re-verify the `query()` async-iteration contract before bumping. |

### Upgrade gotchas

- **Independent semver across languages.** A "we bumped the SDK" change request must specify which language. The two packages do not move in lockstep; matching Python `0.2.90` against TS `0.3.163` is the validated baseline, not the only valid pairing.
- **`anthropic` companion package.** The Python package's `extra_packages: anthropic` pin (`>=0.69.0`) tracks the SDK's own minimum. Pinning `anthropic` separately to a lower version causes `tool_use` content-block schema mismatches that surface as silent missing tool calls. Let the SDK's transitive resolution win.
- **`ClaudeAgentOptions` field renames.** Mid-0.2 the Python field set settled on `system_prompt` / `max_turns` / `subagents_dir`; older drafts that used `systemPrompt` / `maxTurns` will pass type-check but be silently ignored. The TS package uses camelCase canonically.
- **Hook context shape.** `HookContext.tool_input` (Python) and `HookContext.toolInput` (TypeScript) stabilized as the canonical accessor mid-0.2 / mid-0.3. The [hooks](#hooks) examples are the durable shape; older snake_case-on-TS drafts will not match.
- **MCP server config across the language boundary.** The `mcp_servers` (Python) / `mcpServers` (TypeScript) config shape mirrors the Claude Code config format; if you derive it from a Claude Code `.mcp.json` programmatically, normalize the case before passing to the SDK.

### Why these bounds

The Python `0.2.0` floor and the TypeScript `^0.3.0` floor are the current release lines for the two packages — there are no validated older bounds because the API has moved fast enough that pre-floor versions don't import the same options-object shape. The `last_known_good` markers (`0.2.90` Python, `0.3.163` TypeScript) reflect the most recent minor we've verified against the [minimal agent](#minimal-python-agent) and [TypeScript variant](#typescript-variant) examples in this doc. Treat any `>=0.3` (Python) or `>=0.4` (TypeScript) bump as a re-port: the SDK has used major bumps to ship breaking renames, and the recipe burden of catching that in CI is not in place yet.
