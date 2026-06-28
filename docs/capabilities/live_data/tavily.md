---
id: live_data.tavily
kind: live_data
implements:
  port: live_data
  interface_version: "1.0"
layer: agent
provides: [web_search, web_extract]
env_vars: [TAVILY_API_KEY]
docker: null
probe: tavily_search_ping
bootstrap_step: null
provisioning_time: instant
cost_tier: per-call
est_tokens: 500
card:
  name: Tavily (Direct API)
  description: "Tavily web search via direct REST API — same vendor as mcp.tavily without MCP framing."
  capabilities_provided: [web_search, web_extract]
  required_credentials: [TAVILY_API_KEY]
emit_files: []
docs: |
  Tavily Search via direct REST API. The scaffold imports the Tavily SDK and
  emits a `web_search` tool the agent calls. For MCP transport use
  `mcp.tavily`.
tags: [live_data, web-search, hosted]
when_to_load: "recipe declares live_data.tavily"
verification:
  tier: T1
---

# Capability: live_data.tavily

> First-run setup: [`getting-started/tavily.md`](../../getting-started/tavily.md). Vendor: https://docs.tavily.com.

**Used for:** Real-time web search and page extraction directly via the Tavily REST API.

## Local setup

No container — the API is hosted at `https://api.tavily.com`. Add the Tavily SDK to the generated project:

- Python: `tavily-python`
- TypeScript: `@tavily/core`

## Wiring

```yaml
# In a recipe's frontmatter:
capabilities:
  - live_data.tavily
```

The scaffold emits a `web_search` tool in the agent's tool set.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `TAVILY_API_KEY` | *(prompted)* | Tavily API key — stored via keyring |

## Client integration

**Python (tavily-python):**

```python
from tavily import AsyncTavilyClient

client = AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"])

response = await client.search(
    query="agent deployments local bring-up",
    search_depth="basic",
    max_results=5,
    include_answer=False,
)
for hit in response["results"]:
    print(hit["title"], hit["url"], hit["content"][:200])
```

**TypeScript (@tavily/core):**

```ts
import { tavily } from "@tavily/core";

const client = tavily({ apiKey: process.env.TAVILY_API_KEY! });

const response = await client.search("agent deployments local bring-up", {
  searchDepth: "basic",
  maxResults: 5,
});
for (const hit of response.results) {
  console.log(hit.title, hit.url, hit.content.slice(0, 200));
}
```

## Probe

`tavily_search_ping` runs `tavily.search("smoke test")` and asserts a non-empty results array.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 Unauthorized` | Wrong / expired API key | Recreate at https://app.tavily.com; rotate via keyring |
| `429 Too Many Requests` | Free quota exhausted | Upgrade plan or add request backoff with `tenacity.retry` |
| Results all from the same domain | Default search prioritizes high-authority sources | Pass `include_domains` / `exclude_domains` to widen / narrow |
| Empty `content` on results | `include_raw_content: false` (default) | Pass `include_raw_content=True` for full page text (uses more API quota) |

## See also

- [`capabilities/mcp/tavily.md`](../mcp/tavily.md) — MCP-transport alternative
- [`patterns/react/overview.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/patterns/react/overview.md) — typical consumer pattern
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
