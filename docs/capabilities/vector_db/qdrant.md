---
id: vector_db.qdrant
kind: vector_db
provides: [embeddings_store, collection_init]
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
emit_files: []
docs: |
  Qdrant vector DB for RAG retrieval and semantic memory. The bootstrap step
  creates declared collections after `docker_up` so the agent can write
  embeddings on first run.
---

# Capability: vector_db.qdrant

> Deep reference: [`stack/vector-qdrant.md`](../../stack/vector-qdrant.md). This page is the provisioning contract.

**Used for:** vector similarity search for RAG, semantic memory, hybrid filtering.

## Why pick this

Default vector store for self-hosted agents. Best p99 latency in the class, payload filtering is first-class, runs as a single container with a single volume. Pick `vector_db.pgvector` instead if you already run Postgres and your vector count is < ~5M; pick `vector_db.chroma` for prototyping only.

## Local setup

The docker fragment above is merged into the project's `docker-compose.yml` by `agent-scaffold`. The dashboard lands at `http://localhost:6333/dashboard` after `docker compose up -d qdrant`.

## Bootstrap (post docker_up)

`bootstrap_vector_db` reads the recipe's [`bootstrap_config.vector_collections`](../../recipes/SCHEMA.md#bootstrap_configvector_collections) block (or per-capability defaults) and idempotently creates each collection via `qdrant-client`:

```python
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

## Cloud / production

Qdrant Cloud at https://cloud.qdrant.io provides managed clusters. Swap is environment-only: set `QDRANT_URL` to the cluster endpoint and `QDRANT_API_KEY` to the cluster token; no code changes. The `host.*` capability you pick is independent — the agent containers connect out to Qdrant Cloud over HTTPS.

## When to swap it

- **→ `vector_db.pgvector`** if Postgres is already in the stack AND total vector count is under ~5M. One less service to operate.
- **→ `vector_db.chroma`** never in production; only if you're prototyping on a single dev machine without docker.

## See also

- `stack/vector-qdrant.md` — full alternative analysis, config knobs, integration code
- `recipes/docs-rag-qa.md`, `recipes/memory-assistant.md` — recipes that consume this capability
