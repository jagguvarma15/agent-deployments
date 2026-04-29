# Stack pick: MCP (Model Context Protocol)

**Choice:** MCP as the standard tool protocol
**Used for:** Exposing and consuming tools as MCP servers, enabling cross-framework tool reuse

## Why this over alternatives

| Option | Why not |
|--------|---------|
| Framework-native tools | LangChain tools, Pydantic AI tools, and Mastra tools are all framework-specific. MCP tools work across all of them |
| OpenAPI / REST | MCP adds tool discovery (`list-tools`) and a standard invocation contract (`call-tool`) that raw REST doesn't provide |
| Custom RPC | MCP is a Linux Foundation standard with growing ecosystem support |

MCP was chosen because tools built as MCP servers are portable across frameworks. Write a tool once, use it from LangGraph, Pydantic AI, Mastra, or any MCP-compatible client.

## Core concepts

- **MCP Server** -- a service that exposes tools via the MCP protocol (HTTP transport). Implements `list-tools` and `call-tool` endpoints.
- **MCP Client** -- a client that discovers and invokes tools on an MCP server. This repo provides a lightweight client in `common/`.
- **Tool schema** -- each tool has a name, description, and JSON Schema for its parameters. Clients use this schema for LLM tool binding.

## Local setup

MCP servers run as separate services in `docker-compose.yml` (or as sidecar processes):

```yaml
mcp-search:
  build: ./tools/search
  ports:
    - "3001:3001"
```

The agent's `MCPClient` points to the server's URL.

## Integration pattern

### Python

```python
from agent_common.mcp_client import MCPClient

async with MCPClient(base_url="http://localhost:3001") as client:
    # Discover available tools
    tools = await client.list_tools()
    # [{"name": "search", "description": "Search the web", "parameters": {...}}]

    # Call a tool
    result = await client.call_tool("search", {"query": "What is MCP?"})
```

### TypeScript

```typescript
import { MCPClient } from "@agent-deployments/common";

const client = new MCPClient({ baseUrl: "http://localhost:3001" });

// Discover tools
const tools = await client.listTools();

// Call a tool
const result = await client.callTool("search", { query: "What is MCP?" });
```

### Binding MCP tools to an agent

The pattern is: discover tools from MCP server, then register them with your framework:

```python
# Pydantic AI example
from pydantic_ai import Agent

agent = Agent("anthropic:claude-sonnet-4-6-20250514")

async with MCPClient(base_url="http://localhost:3001") as mcp:
    tools = await mcp.list_tools()

    for tool_def in tools:
        @agent.tool_plain
        async def mcp_tool(**kwargs):
            return await mcp.call_tool(tool_def["name"], kwargs)
```

## Client API

### `MCPClient` (Python)

| Method | Args | Returns |
|--------|------|---------|
| `list_tools()` | -- | `list[dict]` -- tool definitions with name, description, parameters |
| `call_tool(name, arguments)` | tool name + args dict | `Any` -- tool result |
| `close()` | -- | Closes the HTTP connection |

Supports `async with` context manager for automatic cleanup.

### `MCPClient` (TypeScript)

| Method | Args | Returns |
|--------|------|---------|
| `listTools()` | -- | `Array<Record<string, unknown>>` |
| `callTool(name, args)` | tool name + args object | `unknown` |

Uses `fetch` with `AbortSignal.timeout` (default: 30s).

## Configuration via env

| Var | Default | Effect |
|-----|---------|--------|
| MCP server URL | `http://localhost:3001` | Per-tool server URL, configured in prototype settings |
| `timeoutMs` / `timeout` | 30s | Request timeout for tool calls |

## Where used in repo

- **`common/python/agent_common/mcp_client/`** -- Python MCP client
- **`common/typescript/src/mcp/`** -- TypeScript MCP client
- **Tests:** `common/python/tests/test_mcp.py`, `common/typescript/tests/mcp.test.ts`
- **Prototypes** -- tools can be implemented as MCP servers and consumed via the client. Currently, most prototypes define tools inline (framework-native); MCP is the path for extracting tools into reusable services.

## Building an MCP server

A minimal MCP server (Python, FastAPI):

```python
from fastapi import FastAPI

app = FastAPI()

TOOLS = [
    {"name": "search", "description": "Search the web", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}},
]

@app.post("/list-tools")
async def list_tools():
    return {"tools": TOOLS}

@app.post("/call-tool")
async def call_tool(request: dict):
    name = request["name"]
    args = request.get("arguments", {})
    if name == "search":
        return {"result": f"Results for: {args.get('query', '')}"}
    return {"error": f"Unknown tool: {name}"}
```
