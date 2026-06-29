---
id: vector_db.chroma
kind: vector_db
implements:
  port: vector_db
  interface_version: "1.0"
layer: data
provides: [embeddings_store, collection_init]
env_vars: [CHROMA_URL, CHROMA_TENANT, CHROMA_DATABASE]
docker:
  service: chroma
  image: chromadb/chroma:0.5.20
  ports: ["8002:8000"]
  volumes: ["chroma_data:/chroma/chroma"]
  healthcheck:
    test: ["CMD-SHELL", "curl -f http://localhost:8000/api/v1/heartbeat || exit 1"]
    interval: 5s
    timeout: 5s
    retries: 5
probe: chroma_heartbeat
bootstrap_step: bootstrap_vector_db
provisioning_time: ~10s
cost_tier: free
est_tokens: 600
card:
  name: Chroma
  description: "Open-source vector DB with single-container deploy and HTTP-only API."
  capabilities_provided: [vector_search, collection_init]
  required_credentials: []
emit_files: []
docs: |
  Chroma vector DB. Smallest install footprint of any vector store option.
  Bootstrap step creates collections after docker_up.
tags: [vector-search, retrieval, self-hosted, embedded]
when_to_load: "recipe declares vector_db.chroma"
stack_docs:
  - stack/vector-qdrant.md
---

# Capability: vector_db.chroma

> Deep reference: [`stack/vector-qdrant.md`](../../stack/vector-qdrant.md). This page is the provisioning contract for the Chroma alternative.

**Used for:** prototype-tier vector storage; in-process embedding workflows.

## Local setup

The docker fragment above is merged into the project's `docker-compose.yml`. Heartbeat probe runs against `/api/v1/heartbeat`.

## Bootstrap (post docker_up)

`bootstrap_vector_db` creates collections via the HTTP API (no client library dep needed):

```python
import httpx
r = httpx.post(
    f"{os.environ['CHROMA_URL']}/api/v1/collections",
    json={"name": "docs", "metadata": {"hnsw:space": "cosine"}},
)
# 200 → created; 409 → already exists; both treated as DONE
```

Optional dep in the generated project: `chromadb` (Python) or fetch directly via the HTTP client.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `CHROMA_URL` | `http://localhost:8002` | HTTP endpoint (host-mapped; in compose use `http://chroma:8000`) |
| `CHROMA_TENANT` | `default_tenant` | Multi-tenant scope |
| `CHROMA_DATABASE` | `default_database` | Database within tenant |

## Client integration

**Python (chromadb):**

```python
import chromadb
client = chromadb.HttpClient(host=os.environ["CHROMA_URL"].replace("http://", "").split(":")[0])
collection = client.get_or_create_collection("docs")

collection.add(
    ids=["1"],
    embeddings=[embedding],
    metadatas=[{"source": "guide.md"}],
    documents=["passage text"],
)

hits = collection.query(query_embeddings=[query_embedding], n_results=5)
```

**TypeScript (chromadb):**

```ts
import { ChromaClient } from "chromadb";
const client = new ChromaClient({ path: process.env.CHROMA_URL! });
const collection = await client.getOrCreateCollection({ name: "docs" });

await collection.add({
  ids: ["1"],
  embeddings: [embedding],
  metadatas: [{ source: "guide.md" }],
  documents: ["passage text"],
});

const hits = await collection.query({ queryEmbeddings: [queryEmbedding], nResults: 5 });
```

## Cloud / production

Chroma Cloud (beta as of 2026) provides hosted instances. For self-hosted production, Chroma scales vertically; pair with a managed reverse proxy for HTTPS termination.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Connection refused 8002` | Container not up yet | `docker compose logs chroma` — heartbeat returns 200 once ready |
| `Collection 'X' does not exist` | `get_collection` called before bootstrap | Use `get_or_create_collection` or re-run `bootstrap_vector_db` |
| Embeddings dimension mismatch | Collection created with default dim, app emits different size | Drop the collection and re-create with the right `dim` in metadata |
| Host port `8002` conflicts with another service | Chroma defaults to host **8002** so the app keeps 8000 (see [port allocation](../../cross-cutting/project-layout.md#9-host-port-allocation)) | Remap in compose, e.g. `ports: ["8004:8000"]`, and update `CHROMA_URL` to match |

## See also

- [`stack/vector-qdrant.md`](../../stack/vector-qdrant.md) — full vector DB analysis
- [`docs/recipes/docs-rag-qa.md`](../../recipes/docs-rag-qa.md) — primary RAG recipe
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
