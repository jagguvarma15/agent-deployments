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

Reference implementations are inline below (formerly `common/python/agent_common/mcp_client/` and `common/typescript/src/mcp/`). Tools can be implemented as MCP servers and consumed via the client. Currently, most agents define tools inline (framework-native); MCP is the path for extracting tools into reusable services.

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

## Reference Implementation

<details>
<summary>Python — <code>client.py</code></summary>

```python
"""MCP (Model Context Protocol) client wrapper with connection management."""

from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class MCPClient:
    """A lightweight MCP client wrapper.

    Usage:
        async with MCPClient(base_url="http://localhost:3001") as client:
            tools = await client.list_tools()
            result = await client.call_tool("search", {"query": "hello"})
    """

    base_url: str
    headers: dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    _http_client: httpx.AsyncClient | None = field(default=None, init=False, repr=False)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=self.timeout,
            )
        return self._http_client

    async def list_tools(self) -> list[dict[str, Any]]:
        """List available tools from the MCP server."""
        client = await self._get_client()
        response = await client.post("/list-tools", json={})
        response.raise_for_status()
        return response.json().get("tools", [])

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call a tool on the MCP server."""
        client = await self._get_client()
        response = await client.post(
            "/call-tool",
            json={"name": name, "arguments": arguments or {}},
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self) -> "MCPClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
```

</details>

<details>
<summary>TypeScript — <code>client.ts</code></summary>

```typescript
/**
 * MCP (Model Context Protocol) client wrapper.
 */

export interface MCPClientConfig {
  baseUrl: string;
  headers?: Record<string, string>;
  timeoutMs?: number;
}

export class MCPClient {
  readonly baseUrl: string;
  readonly headers: Record<string, string>;
  readonly timeoutMs: number;

  constructor(config: MCPClientConfig) {
    this.baseUrl = config.baseUrl;
    this.headers = config.headers ?? {};
    this.timeoutMs = config.timeoutMs ?? 30_000;
  }

  async listTools(): Promise<Array<Record<string, unknown>>> {
    const response = await fetch(`${this.baseUrl}/list-tools`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...this.headers },
      body: JSON.stringify({}),
      signal: AbortSignal.timeout(this.timeoutMs),
    });

    if (!response.ok) {
      throw new Error(`MCP list-tools failed: ${response.status}`);
    }

    const data = (await response.json()) as {
      tools?: Array<Record<string, unknown>>;
    };
    return data.tools ?? [];
  }

  async callTool(
    name: string,
    args: Record<string, unknown> = {},
  ): Promise<unknown> {
    const response = await fetch(`${this.baseUrl}/call-tool`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...this.headers },
      body: JSON.stringify({ name, arguments: args }),
      signal: AbortSignal.timeout(this.timeoutMs),
    });

    if (!response.ok) {
      throw new Error(`MCP call-tool "${name}" failed: ${response.status}`);
    }

    return response.json();
  }
}
```

</details>
