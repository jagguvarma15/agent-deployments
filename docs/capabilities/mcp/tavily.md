---
id: mcp.tavily
kind: mcp
layer: agent
provides: [web_search, web_extract]
env_vars: [TAVILY_API_KEY]
transport: streamable_http
endpoint: https://mcp.tavily.com/mcp/
docker: null
probe: tavily_mcp_ping
bootstrap_step: null
provisioning_time: instant
cost_tier: per-call
est_tokens: 550
card:
  name: Tavily (MCP)
  description: "Tavily web search exposed as an MCP server over streamable_http transport."
  capabilities_provided: [web_search, web_extract]
  required_credentials: [TAVILY_API_KEY]
emit_files: []
docs: |
  Tavily's hosted MCP server. Exposes `tavily_search` and `tavily_extract`
  as MCP tools the agent discovers at session start. For the direct-API
  alternative (no MCP framing) use `live_data.tavily`.
tags: [mcp, web-search, hosted]
when_to_load: "recipe declares mcp_servers with capability: mcp.tavily"
---

# Capability: mcp.tavily

> First-run setup: [`getting-started/tavily.md`](../../getting-started/tavily.md). Vendor: https://docs.tavily.com/documentation/mcp.

**Used for:** Web search and page extraction as MCP-protocol tools the agent discovers at runtime.

## Local setup

No container — the MCP server is hosted at `https://mcp.tavily.com/mcp/`. The agent connects via `streamable_http` with bearer auth using `TAVILY_API_KEY`.

## Wiring

```yaml
# In a recipe's frontmatter:
mcp_servers:
  - id: tavily
    capability: mcp.tavily
    transport: streamable_http
    env:
      TAVILY_API_KEY: required
```

`wire_credentials` prompts for `TAVILY_API_KEY` and stores it via keyring; the generated project reads it at boot.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `TAVILY_API_KEY` | *(prompted)* | Tavily API key — stored via keyring |

## Client integration

Per-framework MCP wiring lives in each framework's `## MCP integration` section ([pydantic-ai](../../frameworks/pydantic-ai.md), [vercel-ai-sdk](../../frameworks/vercel-ai-sdk.md), etc.). The capability-level wiring:

**Python (mcp-client):**

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client(
    "https://mcp.tavily.com/mcp/",
    headers={"Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}"},
) as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        result = await session.call_tool("tavily_search", {"query": "agent deployments"})
```

**TypeScript (@modelcontextprotocol/sdk):**

```ts
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

const transport = new StreamableHTTPClientTransport(
  new URL("https://mcp.tavily.com/mcp/"),
  { requestInit: { headers: { Authorization: `Bearer ${process.env.TAVILY_API_KEY}` } } }
);
const client = new Client({ name: "agent", version: "1.0.0" }, { capabilities: {} });
await client.connect(transport);

const tools = await client.listTools();
const result = await client.callTool({ name: "tavily_search", arguments: { query: "agent deployments" } });
```

## Probe

`tavily_mcp_ping` issues a minimal `tavily_search` call against the streamable_http endpoint and asserts a 200 with a non-empty result. Run by `agent-scaffold doctor` after `wire_credentials`.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 Unauthorized` on connect | Wrong / expired API key | Recreate at https://app.tavily.com; rotate via `agent-scaffold auth login --provider tavily` |
| Tool list is empty | Server connection succeeded but session not initialized | Call `session.initialize()` before `list_tools()` |
| Streaming handshake hangs | Network filtering on `mcp.tavily.com` | Swap to `live_data.tavily` (direct REST) or allowlist the host |
| `429 Too Many Requests` | Free tier quota exhausted | Upgrade plan or add backoff with `tenacity.retry` |

## See also

- [`capabilities/live_data/tavily.md`](../live_data/tavily.md) — direct-API alternative
- [`stack/tool-protocol-mcp.md`](../../stack/tool-protocol-mcp.md) — MCP protocol reference
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
