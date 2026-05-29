---
id: vector_db.chroma
kind: vector_db
provides: [embeddings_store, collection_init]
env_vars: [CHROMA_URL, CHROMA_TENANT, CHROMA_DATABASE]
docker:
  service: chroma
  image: chromadb/chroma:0.5.20
  ports: ["8000:8000"]
  volumes: ["chroma_data:/chroma/chroma"]
  healthcheck:
    test: ["CMD-SHELL", "curl -f http://localhost:8000/api/v1/heartbeat || exit 1"]
    interval: 5s
    timeout: 5s
    retries: 5
probe: chroma_heartbeat
bootstrap_step: bootstrap_vector_db
emit_files: []
docs: |
  Chroma vector DB. Prototype-friendly default with the smallest install
  footprint. Bootstrap step creates collections after docker_up.
---

# Capability: vector_db.chroma

> Deep reference for vector DB choices: [`stack/vector-qdrant.md`](../../stack/vector-qdrant.md). This page is the provisioning contract for the Chroma alternative.

**Used for:** prototype-tier vector storage, in-process embedding workflows.

## Why pick this

Smallest moving parts of any vector DB option — single container, single volume, single HTTP port. Picks itself when the goal is "I want vectors working in five minutes, not five hours." Not the production answer; `vector_db.qdrant` or `vector_db.pgvector` is what you ship.

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
# 200 → created; 409 → already exists, both treated as DONE
```

Optional dep in the generated project: `chromadb` (Python) or fetch directly via the HTTP client.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `CHROMA_URL` | `http://localhost:8000` | HTTP endpoint |
| `CHROMA_TENANT` | `default_tenant` | Multi-tenant scope |
| `CHROMA_DATABASE` | `default_database` | Database within tenant |

## Cloud / production

Chroma Cloud (closed beta as of 2026 Q1) provides hosted instances. For self-hosted production at moderate scale, Chroma scales vertically but lacks the operational story of Qdrant — recommend the swap below.

## When to swap it

- **→ `vector_db.qdrant`** as soon as you go past prototype. Same `Distance.COSINE` semantics, much better filtering and p99.
- **→ `vector_db.pgvector`** if you already run Postgres and want one fewer service.

## See also

- `stack/vector-qdrant.md` — full vector DB alternative analysis
- `recipes/docs-rag-qa.md` — primary RAG recipe
