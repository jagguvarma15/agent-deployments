---
status: Blueprint (design spec)
languages: [python]
agent_pattern: rag
pattern_levels: [overview, architecture, flow, design]
agent_role: "You are a documentation assistant. Answer using only documents retrieved from the data plane and cite each source path; if the corpus does not cover it, say so plainly."
primitives: []
runtime_modes:
  default:
    description: "Anthropic Claude + the arrowhead MCP data plane (corpus, hybrid retrieval, SQL) riding the stack's Postgres. Boots with only ANTHROPIC_API_KEY."
    swaps: {}
    context_budget: {input_max: 80000, output_max: 8000}
  local_only:
    description: "Self-hosted vLLM instead of Anthropic Claude — the arrowhead data plane is unchanged."
    swaps:
      stack/llm-claude: stack/llm-local-vllm
    context_budget: {input_max: 32000, output_max: 4000}
mcp_servers:
  - id: arrowhead
    capability: mcp.arrowhead
    transport: streamable_http
smoke_test:
  ready: "curl -sf http://localhost:8000/health && curl -sf http://127.0.0.1:8004/ready"
  exercise: |
    curl -sf -X POST http://localhost:8000/ask \
      -H 'content-type: application/json' \
      -d '{"question":"What is the canonical stack for this agent?"}'
  assert_jq: '.answer | length > 0'
cost_profile:
  tier: low
  sources: [anthropic]
  typical_run_usd: 0.005
model_recommendation: claude-sonnet-4-6
env_overrides:
  APP_PORT: 8000
  ARROWHEAD_MCP_URL: http://127.0.0.1:8004/mcp
est_tokens: 3600
required_files:
  - Dockerfile
  - docker-compose.yml
  - .github/workflows/ci.yml
  - app/main.py
  - app/agent/qa.py
  - app/tools/mcp_registry.py
  - tests/unit/test_mcp_registry.py
  - tests/integration/test_ask.py
recipe_dependencies:
  python:
    fastapi: ">=0.110.0"
    pydantic-ai: ">=0.0.13"
    pydantic-settings: ">=2.0.0"
    mcp: ">=1.9.0"
    structlog: ">=24.1.0"
external_services:
  - postgres
capabilities:
  - relational.postgres
  - vector_db.pgvector
  - mcp.arrowhead
  - eval.promptfoo
bootstrap_config:
  vector_collections:
    - { name: doc_chunks, vector_size: 1536, distance: cosine }
acceptance_contracts:
  http_endpoints:
    - {path: /health, method: GET, status: 200}
    - {path: /ask, method: POST, status: 200}
  required_env:
    - {name: ANTHROPIC_API_KEY, source: prompted}
    - {name: DATABASE_URL, source: 'capability:relational.postgres'}
  required_compose_services: [postgres, arrowhead]
  smoke_assertions:
    - {jq: '.answer | length > 0', against: smoke_test.exercise.stdout}
topology: single
load_list:
  - {path: https://github.com/jagguvarma15/agent-blueprints/blob/main/patterns/rag/overview.md, required: true}
  - {path: ../frameworks/pydantic-ai.md, required: true}
  - {path: ../cross-cutting/project-layout.md, required: true}
  - {path: ../stack/llm-claude.md, required: true}
  - {path: ../stack/tool-protocol-mcp.md, required: true}
  - {path: ../capabilities/mcp/arrowhead.md, required: true}
  - {path: ../stack/api-fastapi.md, required: false}
  - {path: ../stack/relational-postgres.md, required: false}
  - {path: ../cross-cutting/logging-structured.md, required: false}
  - {path: ../cross-cutting/rate-limiting.md, required: false}
---

# Recipe: docs-rag-arrowhead

**Status:** Blueprint (design spec)

## Composes

- Pattern: [RAG](https://github.com/jagguvarma15/agent-blueprints/blob/main/patterns/rag/overview.md)
- Framework: [Pydantic AI](../frameworks/pydantic-ai.md) (mcp-native; retrieval rides MCP tools)
- Data plane: [Arrowhead](../capabilities/mcp/arrowhead.md) over [MCP](../stack/tool-protocol-mcp.md)
- Stack: [FastAPI](../stack/api-fastapi.md), [Postgres + pgvector](../stack/relational-postgres.md)

## What it does

Documentation Q&A where the agent owns no retrieval code. Every data operation — corpus reads, hybrid retrieval, indexing, scanning — happens on the arrowhead server through MCP tools, behind arrowhead's guards (authorization, rate limits, sanitization, SSRF defenses, audit). The generated app is deliberately thin: a `/ask` endpoint, a Pydantic AI agent, and an MCP session against the data plane.

This is the reference recipe for the `mcp` port with a self-hosted server: it exercises the whole chain the scaffold ships — `mcp_servers` frontmatter, capability resolution, the `bootstrap_mcp` step's `mcp.json` registry, the `mcp_ping` doctor probe, and compose-fragment merging with a pinned image.

## Architecture

```
user -> POST /ask -> Pydantic AI agent (Claude)
                        |  MCP tools via mcp.json registry
                        v
                arrowhead :8004/mcp  (docs profile)
                   |- hybrid_query / vector_query / doc_search
                   |- doc_read (cited answer sources)
                   |- doc_write / doc_index (corpus maintenance)
                        |
                        v
                postgres (pgvector: doc_chunks)
```

- The agent registers arrowhead's tools at startup by reading `mcp.json` (written by the scaffold's `bootstrap_mcp` step), expanding `${VAR}` placeholders from the process env. Absent file or unreachable server degrades to zero MCP tools with a logged warning.
- Retrieval is `hybrid_query` (reciprocal-rank fusion of vector similarity and Postgres full-text rank); the agent follows up with `doc_read` on the top sources so citations quote real paths.
- Corpus documents are seeded by the `seed` step through `doc_write`, then indexed with `doc_index` into the `doc_chunks` collection.

## API contract

| Endpoint | Method | Request | Response |
|----------|--------|---------|----------|
| `/health` | GET | -- | `{"status": "ok"}` |
| `/ask` | POST | `{"question": string}` | `{"answer": string, "sources": [string]}` |

`sources` carries the corpus paths of the documents the answer used, taken from `doc_read` provenance.

## Tool usage (arrowhead, docs profile)

| Tool | Used for |
|------|----------|
| `hybrid_query` | primary retrieval: query -> top-k chunks with source paths |
| `doc_read` | fetch the cited documents' sanitized content |
| `doc_write` + `doc_index` | seeding: write sample docs, chunk + embed into pgvector |
| `doc_search` | fallback literal search when the vector leg is unconfigured |

Note the embedding caveat from the capability doc: arrowhead's default embedder is deterministic and non-semantic, good enough for the smoke test's exact-topic question; point `ARROWHEAD_EMBEDDING_PROVIDER` at a real embedding endpoint for production relevance.

## Key files

| Path | Purpose |
|------|---------|
| `app/main.py` | FastAPI app: `/health`, `/ask`, MCP session lifecycle |
| `app/agent/qa.py` | Pydantic AI agent: system prompt, answer + citation shaping |
| `app/tools/mcp_registry.py` | reads `mcp.json`, expands env placeholders, opens streamable HTTP sessions |
| `mcp.json` | written by the scaffold's `bootstrap_mcp` step — not generated, not hand-edited |
| `scripts/seed.py` | seeds sample corpus docs through `doc_write` (one must answer the smoke question), indexes with `doc_index` when the vector leg is configured |
| `tests/unit/test_mcp_registry.py` | registry parsing, `${VAR}` expansion, missing-file degradation |
| `tests/integration/test_ask.py` | end-to-end `/ask` against the compose stack |

## Environment & deployment

Local: `agent-scaffold up --docker` brings up `postgres` and `arrowhead` (loopback-bound `8004`, auth off — safe only because of the loopback binding), runs the pgvector bootstrap for `doc_chunks`, seeds the corpus, and launches the backend on `8000`. `agent-scaffold doctor` probes arrowhead with `mcp_ping` and Postgres with `postgres_select_one`.

Deployed: enable arrowhead's OAuth 2.1 resource-server auth (`ARROWHEAD_AUTH_ENABLED` plus `ARROWHEAD_OAUTH_*`), drop the insecure-HTTP override, and put a bearer token on the MCP session; the `mcp.json` entry then carries an `Authorization` header placeholder.

## Test strategy

- Unit: registry reader (placeholder expansion, absent-file degradation), citation shaping.
- Integration: `/ask` round-trip against the live stack; asserts the answer is grounded in a seeded document and `sources` is non-empty.
- Eval: `eval.promptfoo` grounding checks — answers must quote only seeded corpus content and decline questions the corpus does not cover.

## Design decisions

- **Data plane over in-app retrieval.** The retrieval stack (chunking, embedding, fusion, sanitization, tenancy) lives server-side and is reused by every agent that binds the capability; the generated project stays small and the security surface is centralized where it is tested.
- **Loopback auth-off locally.** Matches the capability doc's pairing rule; production keeps full OAuth. The recipe never writes credentials into `mcp.json` — placeholders only.
- **Design spec until the image ships.** The capability's compose fragment pins a GHCR image that publishes on arrowhead's release tag; this recipe flips to `Blueprint (validated)` once the end-to-end run passes against the published image.
