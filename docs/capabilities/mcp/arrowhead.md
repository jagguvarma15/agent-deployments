---
id: mcp.arrowhead
kind: mcp
implements:
  port: mcp
  interface_version: "1.0"
layer: agent
requires: [relational.postgres, vector_db.pgvector]
provides:
  [
    document_store,
    hybrid_search,
    semantic_search,
    sql_query,
    http_fetch,
    background_tasks,
    agent_memory,
    kv_store,
  ]
env_vars: []
transport: streamable_http
endpoint: http://127.0.0.1:8004/mcp
docker:
  service: arrowhead
  image: ghcr.io/jagguvarma15/arrowhead:0.2.832
  ports: ["127.0.0.1:8004:8000"]
  volumes: ["arrowhead_corpus:/app/documents"]
  environment:
    ARROWHEAD_TRANSPORT: http
    ARROWHEAD_HOST: 0.0.0.0
    ARROWHEAD_PORT: "8000"
    ARROWHEAD_PROFILE: "${ARROWHEAD_PROFILE:-docs}"
    ARROWHEAD_AUTH_ENABLED: "false"
    ARROWHEAD_ALLOW_INSECURE_HTTP: "true"
    ARROWHEAD_DOCS_ROOT: /app/documents
    ARROWHEAD_SQL_DSN: "postgresql+asyncpg://${POSTGRES_USER:-agent}:${POSTGRES_PASSWORD:-agent}@postgres:5432/${POSTGRES_DB:-agent_db}"
  healthcheck:
    test:
      [
        "CMD",
        "python",
        "-c",
        "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)",
      ]
    interval: 15s
    timeout: 5s
    retries: 5
probe: mcp_ping
bootstrap_step: null
provisioning_time: ~15s
cost_tier: free
est_tokens: 700
card:
  name: Arrowhead
  description: "Hardened MCP data plane: document corpus, hybrid and semantic retrieval, read-only SQL, SSRF-guarded fetch, and background scans behind per-caller guards."
  capabilities_provided:
    [
      document_store,
      hybrid_search,
      semantic_search,
      sql_query,
      http_fetch,
      background_tasks,
      agent_memory,
      kv_store,
    ]
  required_credentials: []
emit_files: []
docs: |
  Self-hosted MCP server over streamable_http. The `docs` profile exposes the
  corpus tools (read, write, search, scan), SQL, pgvector and hybrid
  retrieval, handle-based background scans, cross-session memory, and KV
  state; every tool runs behind guards for rate limiting, authorization,
  sanitization, and audit.
tags: [mcp, retrieval, documents, sql, self-hosted]
when_to_load: "recipe declares mcp_servers with capability: mcp.arrowhead"
stack_docs:
  - stack/tool-protocol-mcp.md
---

# Capability: mcp.arrowhead

> Server repo: https://github.com/jagguvarma15/arrowhead. Deep protocol reference: [`stack/tool-protocol-mcp.md`](../../stack/tool-protocol-mcp.md).

**Used for:** a secure data plane the agent talks to over MCP — a writable document corpus with literal, semantic (pgvector), and hybrid (reciprocal-rank-fusion) retrieval, vetted read-only SQL, SSRF-guarded URL fetch, secrets-and-PII scanning, and handle-based background tasks.

## Local setup

Runs as the compose service above. The host port is `8004` (the agent backend owns `8000`; see the allocation table in [`cross-cutting/project-layout.md`](../../cross-cutting/project-layout.md)), bound to loopback because the local stack runs with auth off; the explicit `ARROWHEAD_ALLOW_INSECURE_HTTP` override exists only because of that loopback pairing.

The `docs` profile keeps the tool list lean: corpus, retrieval, SQL, fetch, task, memory, and webhook-notify tools — no code execution surface. The compose fragment reads the profile as `${ARROWHEAD_PROFILE:-docs}`, so a recipe or environment can select another profile (for example `coding`) without editing the fragment. SQL and vector retrieval ride the stack's Postgres (`requires: relational.postgres, vector_db.pgvector`); arrowhead's chunk table schema (`doc_chunks` with tenant, content-hash, and tsvector columns) is applied by the recipe's bootstrap, not by this capability.

- A backend running as a host process reaches the server at `http://127.0.0.1:8004/mcp`.
- A backend running inside compose uses `http://arrowhead:8000/mcp` (service name, container port).

## Production auth

The dev-insecure pairing above (loopback binding plus `ARROWHEAD_ALLOW_INSECURE_HTTP: "true"`) is for local stacks only. A deployed stack switches the server to OAuth 2.1 resource-server mode:

- `ARROWHEAD_AUTH_ENABLED: "true"` and drop `ARROWHEAD_ALLOW_INSECURE_HTTP` entirely — the server refuses unauthenticated HTTP by default.
- `ARROWHEAD_OAUTH_PROVIDER: jwt` with `ARROWHEAD_OAUTH_ISSUER`, `ARROWHEAD_OAUTH_AUDIENCE`, and `ARROWHEAD_OAUTH_JWKS_URI` pointing at the identity provider (an AuthKit domain is also supported).
- The server publishes RFC 9728 protected-resource metadata at `/.well-known/oauth-protected-resource/mcp`; clients discover the authorization server from it.
- Access is scoped per tool family — see the scope table in the server repo's auth docs to grant callers only the families the recipe uses.

## Wiring

```yaml
# In a recipe's frontmatter:
mcp_servers:
  - id: arrowhead
    capability: mcp.arrowhead
    transport: streamable_http
```

No credentials are required locally, so `wire_credentials` has nothing to prompt for. The scaffold's `bootstrap_mcp` step writes the server into the generated project's `mcp.json` registry.

## Tools exposed (docs profile)

`safe_fetch`, `calculate`, `read_file`, `doc_search`, `doc_read`, `doc_retrieve`, `doc_scan`, `doc_write`, `sql_query`, `vector_search`, `vector_query`, `hybrid_query`, `doc_index`, `scan_corpus_async`, `task_get`, `task_update`, `task_list`, `task_schedule`, the memory family (`memory_store`, `memory_search`, `memory_list`, `memory_delete`, `kv_set`, `kv_get`, `kv_delete`), and `notify_webhook` (registers only when `ARROWHEAD_NOTIFY_ALLOWLIST` is set — a second opt-in on top of the profile), plus the `docs://index` and `doc://{+path}` resources and an `arrowhead://integrity` digest a client can pin. `arrowhead list-tools --json` prints the exact catalog with input schemas.

## Client integration

Per-framework MCP wiring lives in each framework's `## MCP integration` section. The capability-level wiring:

**Python (official `mcp` SDK, v2):**

```python
from mcp import Client

async with Client("http://127.0.0.1:8004/mcp") as client:
    tools = (await client.list_tools()).tools
    result = await client.call_tool("hybrid_query", {"query": "refund policy", "top_k": 5})
```

When the deployed server requires auth, open the transport with a bearer-carrying
`httpx.AsyncClient` and run a `ClientSession` over it:

```python
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

http = httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"})
async with streamable_http_client("https://arrowhead.example/mcp", http_client=http) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
```

**TypeScript (@modelcontextprotocol/sdk):**

```ts
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

const transport = new StreamableHTTPClientTransport(new URL("http://127.0.0.1:8004/mcp"));
const client = new Client({ name: "agent", version: "1.0.0" }, { capabilities: {} });
await client.connect(transport);

const tools = await client.listTools();
const result = await client.callTool({
  name: "hybrid_query",
  arguments: { query: "refund policy", top_k: 5 },
});
```

## Probe

`mcp_ping` posts a JSON-RPC `initialize` to the streamable_http endpoint and asserts a 2xx handshake. Run by `agent-scaffold doctor`; the container's own healthcheck probes `/health`, and `/ready` additionally reports corpus writability and the SQL backend.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| Container exits at startup | HTTP transport with auth off and no insecure override | Keep `ARROWHEAD_ALLOW_INSECURE_HTTP: "true"` paired with the loopback port binding |
| `vector_query` returns irrelevant results | Default embedder is deterministic (non-semantic) | Set `ARROWHEAD_EMBEDDING_PROVIDER: http` and point `ARROWHEAD_EMBEDDING_ENDPOINT` at a real embedding service |
| `sql_query` refuses with "not configured" | `ARROWHEAD_SQL_DSN` unset or Postgres not up | Check the `postgres` service is healthy and the DSN matches its credentials |
| `doc_index` denied | The `ingest` action is not in the default authorization policy | Grant it via `ARROWHEAD_AUTHZ_POLICY` for the indexing caller |
| Tool missing from `tools/list` | Outside the active profile, or disabled | Check `ARROWHEAD_PROFILE` and `ARROWHEAD_DISABLED_TOOLS` |

## See also

- [`capabilities/vector_db/pgvector.md`](../vector_db/pgvector.md) — the extension arrowhead's retrieval rides on
- [`capabilities/relational/postgres.md`](../relational/postgres.md) — the shared Postgres service
- [`stack/tool-protocol-mcp.md`](../../stack/tool-protocol-mcp.md) — MCP protocol reference
