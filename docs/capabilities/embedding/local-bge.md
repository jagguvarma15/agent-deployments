---
id: embedding.local-bge
kind: embedding
implements:
  port: embedding
  interface_version: "1.0"
layer: agent
provides: [text_embeddings, local_inference]
env_vars: [EMBEDDINGS_URL]
model: BAAI/bge-m3
dimensions: 1024
hosting: [docker]
docker:
  service: embeddings
  image: ghcr.io/huggingface/text-embeddings-inference:cpu-1.6
  # TEI's CPU images publish amd64 only (no arm64 manifest through cpu-latest).
  # Pinning the platform runs the service under emulation on Apple Silicon
  # instead of hard-failing the pull; on amd64 hosts it matches native and is
  # a no-op.
  platform: linux/amd64
  environment:
    MODEL_ID: BAAI/bge-m3
  ports: ["8080:80"]
  volumes: ["tei_data:/data"]
  healthcheck:
    test: ["CMD-SHELL", "wget -qO- http://localhost:80/health || exit 1"]
    interval: 10s
    timeout: 5s
    retries: 10
probe: null
bootstrap_step: null
provisioning_time: ~60s first run (model download), instant after
cost_tier: free
est_tokens: 550
card:
  name: Local BGE-M3 embeddings
  description: "BAAI/bge-m3 (1024 dim) served by Text Embeddings Inference in a local container — no API key, no per-call cost, data never leaves the machine."
  capabilities_provided: [text_embeddings, local_inference]
  required_credentials: []
emit_files: []
docs: |
  BGE-M3 embeddings served locally by Hugging Face Text Embeddings Inference
  (TEI). The generated project calls the OpenAI-compatible /v1/embeddings
  endpoint at EMBEDDINGS_URL (default http://localhost:8080) — no API key
  and no per-call cost, and documents never leave the machine. 1024-dim
  dense output: recipe-side vector_collections must declare dimensions:
  1024 when pairing with this capability (the pgvector/qdrant bootstrap
  reads the declared dimension). The first docker_up downloads the model
  (~2 GB) into the tei_data volume; later runs start in seconds.
tags: [embeddings, local, self-hosted, bge, tei]
when_to_load: "recipe declares embedding.local-bge"
stack_docs:
  - stack/llm-claude.md
---

# Capability: embedding.local-bge

> Vendor: https://huggingface.co/BAAI/bge-m3 · Serving: https://github.com/huggingface/text-embeddings-inference

**Used for:** Generating text embeddings for vector-DB ingestion and query-side encoding without an external embedding API — offline-capable, free per call, and private by construction.

## Local setup

The docker fragment runs Text Embeddings Inference (CPU image) serving
`BAAI/bge-m3`. The first `docker_up` downloads the model into the `tei_data`
volume (roughly 2 GB; allow ~60s); subsequent starts are seconds. No
credentials are required at any point.

The generated project needs no vendor SDK — TEI exposes an OpenAI-compatible
`/v1/embeddings` endpoint, so the standard HTTP client (or the OpenAI SDK
pointed at `EMBEDDINGS_URL`) works in both languages.

## Wiring

```yaml
# In a recipe's frontmatter:
capabilities: [vector_db.pgvector, embedding.local-bge]
```

The scaffold wires the embedding client into the indexing step and the query
encoder exactly as it does for `embedding.openai` — the two are drop-in
swaps at the capability level. The dimension differs: BGE-M3 emits **1024**
dims (OpenAI's small model emits 1536), so the recipe's declared
`vector_collections` dimensions must match whichever embedding capability is
active.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `EMBEDDINGS_URL` | `http://localhost:8080` | TEI endpoint the generated project calls |

Configuration, not a credential — no keyring entry, no prompt.

## When to prefer this over embedding.openai

- No external API dependency or key for the RAG path.
- Documents and queries never leave the machine (compliance-sensitive corpora).
- Zero per-call cost for high-volume ingestion.

Prefer `embedding.openai` when the deploy target cannot run a container or
the corpus is small enough that hosted-API simplicity wins.
