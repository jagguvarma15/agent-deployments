---
id: live_data.tavily
kind: live_data
provides: [web_search, web_extract]
env_vars: [TAVILY_API_KEY]
docker: null
probe: tavily_search_ping
bootstrap_step: null
emit_files: []
docs: |
  Tavily Search via direct REST API (no MCP framing). The scaffold imports
  the Tavily Python / TS SDK and emits a `web_search` tool the agent can
  call. For frameworks that natively speak MCP (Claude Agent SDK, Cursor,
  Mastra), prefer `mcp.tavily` instead — same vendor, MCP transport.
---

# Capability: live_data.tavily

> First-run setup: [`getting-started/tavily.md`](../../getting-started/tavily.md). Vendor: https://docs.tavily.com.

**Used for:** Real-time web search and page-extraction directly via the Tavily REST API.

## Why pick this

When the recipe's framework doesn't speak MCP, or when you want one less moving part (no MCP server / transport layer). Tavily's search is tuned for agent use: ranked snippets, source URLs, raw + cleaned content, optional follow-up question hints. Lower latency than the MCP path on a per-call basis (no MCP handshake) but you lose discoverability.

For the MCP-native alternative, see `mcp.tavily`.

## Wiring

```yaml
# In a recipe's frontmatter:
capabilities:
  - live_data.tavily
```

The scaffold emits a `web_search(query, **opts)` tool in the agent's tool set. No additional recipe fields required.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `TAVILY_API_KEY` | *(prompted)* | Tavily API key — stored via keyring |

## Probe

`tavily_search_ping` runs `tavily.search("agent-deployments smoke test")` and asserts a non-empty results array.

## When to swap it

- **→ `mcp.tavily`** — same vendor, MCP transport.
- **→ `live_data.brave-search`** — different search backend, similar API shape.
- **→ `live_data.serper`** — Google-results-as-API.

## See also

- [`mcp/tavily.md`](../mcp/tavily.md) — MCP-transport alternative.
- [`vendored/blueprints/patterns/react/overview.md`](../../../vendored/blueprints/patterns/react/overview.md) — typical consumer pattern.
