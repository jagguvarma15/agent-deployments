# Tavily

> Web search + page extraction for agents. Used by both `mcp.tavily` (MCP transport) and `live_data.tavily` (direct REST API).

**Signup**: https://app.tavily.com

## Create a key

1. Open the dashboard at https://app.tavily.com
2. Top-right menu → **API Keys** → **Create Key**. Name it after the env that will use it (`laptop-2026`, `ci-prod`).
3. Copy the key — it starts with `tvly-` and is shown **once**. The dashboard also exposes a free monthly quota; the key works inside that envelope without a payment method.

## Wire into your project

```bash
# Recommended: store in OS keychain via agent-scaffold
agent-scaffold auth login --provider tavily

# Or shell env (ends up in history):
export TAVILY_API_KEY='tvly-...'
```

Pick one capability:

- **MCP transport** (Claude Agent SDK, Cursor, Mastra): declare `mcp_servers: [{id: tavily, capability: mcp.tavily, transport: streamable_http, env: {TAVILY_API_KEY: required}}]` in the recipe.
- **Direct REST** (everything else): declare `capabilities: [live_data.tavily]` and the scaffold emits a `web_search` tool.

## Verify

```bash
curl -sS -X POST https://api.tavily.com/search \
  -H "Content-Type: application/json" \
  -d "{\"api_key\":\"$TAVILY_API_KEY\",\"query\":\"smoke test\"}" | head -50
```

A `200` with a `results` array means you're good.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 Unauthorized` | Key revoked or typo | Recreate in dashboard |
| `429 Too Many Requests` | Free quota exhausted | Add billing in dashboard, raise plan |
| MCP handshake hang | Network filtering on `mcp.tavily.com` | Allowlist; or swap to `live_data.tavily` |

## See also

- [`docs/capabilities/mcp/tavily.md`](../capabilities/mcp/tavily.md) — MCP-transport capability.
- [`docs/capabilities/live_data/tavily.md`](../capabilities/live_data/tavily.md) — direct-API capability.
