---
id: vector_db.qdrant
kind: vector_db
layer: data
provides: [embeddings_store, collection_init, payload_filtering]
env_vars: [QDRANT_URL, QDRANT_API_KEY]
docker:
  service: qdrant
  image: qdrant/qdrant:v1.12.0
  ports: ["6333:6333", "6334:6334"]
  volumes: ["qdrant_data:/qdrant/storage"]
  healthcheck:
    test: ["CMD-SHELL", "wget -qO- http://localhost:6333/healthz || exit 1"]
    interval: 5s
    timeout: 5s
    retries: 5
probe: qdrant_collections
bootstrap_step: bootstrap_vector_db
provisioning_time: ~10s
cost_tier: free
est_tokens: 750
card:
  name: Qdrant
  description: "Self-hosted vector DB with REST + gRPC endpoints, named collections, and payload filtering."
  capabilities_provided: [vector_search, hybrid_search, payload_filtering, collection_init]
  required_credentials: []
emit_files: []
docs: |
  Qdrant vector DB for RAG retrieval and semantic memory. The bootstrap step
  creates declared collections after `docker_up` so the agent can write
  embeddings on first run.
tags: [vector-search, retrieval, self-hosted]
when_to_load: "recipe declares vector_db.qdrant"
---

# Capability: vector_db.qdrant

> Deep reference: [`stack/vector-qdrant.md`](../../stack/vector-qdrant.md). This page is the provisioning contract.

**Used for:** vector similarity search for RAG, semantic memory, hybrid filtering.

## Local setup

The docker fragment above is merged into the project's `docker-compose.yml`. Dashboard at `http://localhost:6333/dashboard` after `docker compose up -d qdrant`.

## Bootstrap (post docker_up)

`bootstrap_vector_db` reads the recipe's [`bootstrap_config.vector_collections`](../../recipes/SCHEMA.md#bootstrap_configvector_collections) block (or per-capability defaults) and idempotently creates each collection via `qdrant-client`:

```python
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

client = QdrantClient(url=os.environ["QDRANT_URL"])
existing = {c.name for c in client.get_collections().collections}
if "docs" not in existing:
    client.create_collection(
        collection_name="docs",
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    )
```

Optional dep in the generated project: `qdrant-client` (Python) or `@qdrant/js-client-rest` (TypeScript).

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `QDRANT_URL` | `http://localhost:6333` | REST endpoint; switch to gRPC (`:6334`) for high-throughput indexing |
| `QDRANT_API_KEY` | *(unset locally)* | Required for Qdrant Cloud; ignored by the self-hosted image |

## Client integration

**Python (qdrant-client):**

```python
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct

client = AsyncQdrantClient(url=os.environ["QDRANT_URL"])

# Upsert
await client.upsert(
    collection_name="docs",
    points=[PointStruct(id=1, vector=embedding, payload={"source": "guide.md"})],
)

# Search
hits = await client.search(
    collection_name="docs",
    query_vector=query_embedding,
    limit=5,
    query_filter={"must": [{"key": "source", "match": {"value": "guide.md"}}]},
)
```

**TypeScript (@qdrant/js-client-rest):**

```ts
import { QdrantClient } from "@qdrant/js-client-rest";
const client = new QdrantClient({ url: process.env.QDRANT_URL! });

await client.upsert("docs", {
  points: [{ id: 1, vector: embedding, payload: { source: "guide.md" } }],
});

const hits = await client.search("docs", {
  vector: queryEmbedding,
  limit: 5,
  filter: { must: [{ key: "source", match: { value: "guide.md" } }] },
});
```

## Cloud / production

Qdrant Cloud at https://cloud.qdrant.io provides managed clusters. Swap is environment-only: set `QDRANT_URL` to the cluster endpoint and `QDRANT_API_KEY` to the cluster token; no code changes.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Connection refused 6333` | Container not up yet | `docker compose logs qdrant` — wait for "qdrant started" |
| `Collection 'X' not found` | Bootstrap didn't run before agent boot | Re-run `bootstrap_vector_db`; verify `bootstrap_config.vector_collections` declares this name |
| Search returns empty payloads | Vectors upserted without `payload` field | Pass `payload={...}` in `PointStruct`; existing points need re-upsert |
| Slow first query | HNSW index cold | First few queries warm the index; bench after `>=100` queries |

## See also

- [`stack/vector-qdrant.md`](../../stack/vector-qdrant.md) — full reference + alternative analysis
- [`docs/recipes/docs-rag-qa.md`](../../recipes/docs-rag-qa.md), [`docs/recipes/memory-assistant.md`](../../recipes/memory-assistant.md) — consumer recipes
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
