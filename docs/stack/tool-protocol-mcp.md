---
tags: [mcp, tool-protocol]
when_to_load: "recipe uses MCP tooling"
---

# Stack pick: MCP (Model Context Protocol)

**Choice:** MCP as the standard tool protocol
**Used for:** Exposing and consuming tools as MCP servers, enabling cross-framework tool reuse

## Why this over alternatives

| Option | Why not |
|--------|---------|
| Framework-native tools | LangChain tools, Pydantic AI tools, and Mastra tools are all framework-specific. MCP tools work across all of them |
| OpenAPI / REST | MCP adds tool discovery (`tools/list`) and a standard invocation contract (`tools/call`) that raw REST doesn't provide |
| Custom RPC | MCP is a Linux Foundation standard with growing ecosystem support |

MCP was chosen because tools built as MCP servers are portable across frameworks. Write a tool once, use it from LangGraph, Pydantic AI, Mastra, or any MCP-compatible client.

## Core concepts

- **Wire protocol** — JSON-RPC 2.0. A session opens with an `initialize` handshake, then the client calls `tools/list` to discover tools and `tools/call` to invoke one. These are JSON-RPC methods on one endpoint, not separate REST routes.
- **Transports** — `stdio` (the client spawns the server as a subprocess; local, single-tenant) and `streamable_http` (one HTTP endpoint, typically `/mcp`, serving JSON or an event stream; remote or shared). The catalog's `mcp.*` capabilities declare which they speak.
- **MCP server** — a service exposing tools (and optionally resources and prompts) over the protocol. Hosted (`mcp.tavily`) or self-hosted in the compose stack (`mcp.arrowhead`).
- **MCP client** — the agent side. Use the official SDKs (`mcp` on PyPI, `@modelcontextprotocol/sdk` on npm) rather than hand-rolling the JSON-RPC; sessions, streams, and protocol-version negotiation are easy to get subtly wrong.
- **Tool schema** — each tool has a name, description, and JSON Schema for its parameters, carried in the `tools/list` response. Clients use this schema for LLM tool binding.

## Local setup

A recipe binds servers through its `mcp_servers:` frontmatter; each entry names an `mcp.*` capability. A self-hosted capability contributes its compose service automatically, and the scaffold's `bootstrap_mcp` step writes every bound server into the generated project's `mcp.json` registry (transport, url, headers, env var names — never values). The generated backend reads that registry at boot and registers each server with its framework's MCP support.

```yaml
# In a recipe's frontmatter:
mcp_servers:
  - id: arrowhead
    capability: mcp.arrowhead
    transport: streamable_http
```

## Integration pattern

### Python (official `mcp` SDK)

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client("http://127.0.0.1:8004/mcp") as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        result = await session.call_tool("hybrid_query", {"query": "What is MCP?"})
```

For a server that requires auth, pass `headers={"Authorization": f"Bearer {token}"}` to `streamablehttp_client`.

### TypeScript (official `@modelcontextprotocol/sdk`)

```typescript
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

const transport = new StreamableHTTPClientTransport(new URL("http://127.0.0.1:8004/mcp"));
const client = new Client({ name: "agent", version: "1.0.0" }, { capabilities: {} });
await client.connect(transport);

const tools = await client.listTools();
const result = await client.callTool({ name: "hybrid_query", arguments: { query: "What is MCP?" } });
```

### Binding MCP tools to an agent

Prefer the framework's native MCP support over manual binding — each framework doc's `## MCP integration` section shows its idiom (`agent.run_mcp_servers()` for Pydantic AI, `mcp_servers` options for the Claude Agent SDK, adapter packages for LangGraph). Where a framework has no native support, discover with `tools/list` and register each tool with a thin forwarding function:

```python
# Pydantic AI, wiring discovered MCP tools manually:
from pydantic_ai import Agent

agent = Agent("anthropic:claude-sonnet-4-6")

for tool in (await session.list_tools()).tools:
    def forward(tool_name: str):
        async def call(**kwargs):
            return await session.call_tool(tool_name, kwargs)
        return call

    agent.tool_plain(name=tool.name)(forward(tool.name))
```

## Configuration via env

| Var | Default | Effect |
|-----|---------|--------|
| Server URL | from the capability's `endpoint` | Written into `mcp.json`; override per deployment |
| Credentials | named per capability (`env_vars`) | `mcp.json` carries `${VAR}` placeholders; the backend expands them from its process env |

## Where used in repo

The `mcp` port (`docs/ports/mcp.md`) is realized by the `mcp.*` capabilities: `mcp.tavily` (hosted web search) and `mcp.arrowhead` (self-hosted data plane). Recipes opt in via `mcp_servers:`; the frameworks matrix marks which frameworks are mcp-native.

## Building an MCP server

Use an SDK, not raw HTTP routes. Minimal Python server with the official SDK:

```python
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("search-tools")

@mcp.tool()
async def search(query: str) -> str:
    """Search the web."""
    return f"Results for: {query}"

if __name__ == "__main__":
    mcp.run()  # stdio by default; streamable HTTP via the http transport
```

The SDK derives the tool schema from the signature and docstring, speaks both transports, and keeps the handshake and protocol-version negotiation correct as the spec evolves. For a production-shaped example — auth, per-caller authorization, rate limits, sanitization, audit — see the arrowhead server (`docs/capabilities/mcp/arrowhead.md`).
