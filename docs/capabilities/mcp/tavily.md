---
id: mcp.tavily
kind: mcp
provides: [web_search, web_extract]
env_vars: [TAVILY_API_KEY]
transport: streamable_http
endpoint: https://mcp.tavily.com/mcp/
docker: null
probe: tavily_mcp_ping
bootstrap_step: null
emit_files: []
docs: |
  Tavily's hosted MCP server. Exposes `tavily_search` and `tavily_extract` as
  MCP tools the agent can call without a local process. Recipes wire it via
  `mcp_servers: [{id: tavily, capability: mcp.tavily, transport: streamable_http,
  env: {TAVILY_API_KEY: required}}]`. For the direct-API alternative (no MCP
  framing), use `live_data.tavily` instead.
---

# Capability: mcp.tavily

> First-run setup: [`getting-started/tavily.md`](../../getting-started/tavily.md). Vendor: https://docs.tavily.com/documentation/mcp.

**Used for:** Web search and page-extraction tools delivered over MCP.

## Why pick this

When the recipe is built on a framework that natively speaks MCP (Claude Agent SDK, Cursor, Claude Desktop, Mastra), wiring the search via MCP lets the agent discover the tools at session start instead of importing a vendor SDK at code-emit time. Trades a network hop for portability.

If the framework doesn't speak MCP, pick `live_data.tavily` instead — same vendor, direct API.

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

The scaffold's `wire_credentials` step prompts for `TAVILY_API_KEY` and stores it via keyring; the generated project reads it at boot.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `TAVILY_API_KEY` | *(prompted)* | Tavily API key — stored via keyring |

## Probe

`tavily_mcp_ping` issues a minimal `tavily_search` call against the streamable_http endpoint and asserts a 200 with a non-empty result. Run by `agent-scaffold doctor` after `wire_credentials`.

## When to swap it

- **→ `live_data.tavily`** — same vendor, direct REST API (no MCP framing).
- **→ `mcp.brave-search`** — same shape, different search backend.

## See also

- [`live_data/tavily.md`](../live_data/tavily.md) — direct-API alternative.
- [`stack/tool-protocol-mcp.md`](../../stack/tool-protocol-mcp.md) — MCP protocol reference.
