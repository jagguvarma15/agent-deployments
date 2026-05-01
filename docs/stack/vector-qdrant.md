# Stack pick: Qdrant

**Choice:** Qdrant 1.12, self-hosted via Docker
**Used for:** Vector similarity search for RAG retrieval, semantic memory

## Why this over alternatives

| Option | Why not |
|--------|---------|
| Pinecone | Managed-only, vendor lock-in, can't run offline with `make up` |
| Weaviate | Heavier resource footprint, more complex schema model for simple retrieval |
| pgvector | Fine for < 5M vectors, but Qdrant has better p99 latency and filtering. pgvector is the swap when Postgres is already present and scale is small |
| Chroma | Designed for prototyping, not production workloads. No built-in clustering |
| Milvus | Powerful but operationally complex for self-hosted. Overkill for single-node agent use cases |

## Local setup

Qdrant is defined in the [Docker Compose template](../reference/docker-compose-template.md):

```yaml
qdrant:
  image: qdrant/qdrant:v1.12.0
  ports:
    - "${QDRANT_HTTP_PORT:-6333}:6333"   # REST API
    - "${QDRANT_GRPC_PORT:-6334}:6334"   # gRPC (higher throughput)
  volumes:
    - qdrant_data:/qdrant/storage
  healthcheck:
    test: ["CMD-SHELL", "wget -qO- http://localhost:6333/healthz || exit 1"]
    interval: 5s
    timeout: 5s
    retries: 5
```

Dashboard available at `http://localhost:6333/dashboard` once running.

## Config knobs that matter

| Knob | Default | Effect |
|------|---------|--------|
| `QDRANT_HTTP_PORT` | 6333 | REST API port |
| `QDRANT_GRPC_PORT` | 6334 | gRPC port (use for high-throughput indexing) |
| Collection distance | `Cosine` | Similarity metric. Cosine for normalized embeddings, Dot for unnormalized |
| `on_disk` | false | Store vectors on disk for large collections (> 1M vectors) |
| HNSW `m` | 16 | Higher = better recall, more memory. 16 is a good default |
| HNSW `ef_construct` | 100 | Higher = better index quality, slower builds |

## Integration pattern

### Python

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

client = QdrantClient(url="http://localhost:6333")

# Create collection
client.create_collection(
    collection_name="docs",
    vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
)

# Upsert vectors
client.upsert(
    collection_name="docs",
    points=[
        PointStruct(id=1, vector=[0.1, 0.2, ...], payload={"text": "chunk text"}),
    ],
)

# Search
results = client.query_points(
    collection_name="docs",
    query=[0.1, 0.2, ...],
    limit=5,
)
```

### TypeScript

```typescript
import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ url: "http://localhost:6333" });

// Create collection
await client.createCollection("docs", {
  vectors: { size: 1536, distance: "Cosine" },
});

// Upsert
await client.upsert("docs", {
  points: [{ id: 1, vector: [0.1, 0.2], payload: { text: "chunk text" } }],
});

// Search
const results = await client.query("docs", {
  query: [0.1, 0.2],
  limit: 5,
});
```

## Where used in repo

- **[Docker Compose template](../reference/docker-compose-template.md)** -- Qdrant service definition
- **[docs-rag-qa](../recipes/docs-rag-qa.md)** -- Primary use case: document chunk storage and retrieval. The blueprint includes an in-memory mock retriever; production swap points to Qdrant via the `QDRANT_URL` and `QDRANT_COLLECTION` settings
- **[memory-assistant](../recipes/memory-assistant.md)** -- Semantic memory storage via Qdrant
- **Settings:** Each blueprint that uses Qdrant exposes `QDRANT_URL` and `QDRANT_COLLECTION` env vars

## Swapping to pgvector

If you already have Postgres and your vector count is under ~5M:

1. Remove the `qdrant` service from `docker-compose.yml`
2. Add pgvector extension: `CREATE EXTENSION vector;`
3. Add a vector column to your chunks table
4. Replace Qdrant client calls with SQLAlchemy + pgvector queries
5. No change to the agent logic -- only the retriever module changes

This is a **multi-file swap** (retriever + docker-compose + DB migration).
