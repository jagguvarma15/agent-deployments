---
id: embedding.openai
kind: embedding
provides: [text_embeddings]
env_vars: [OPENAI_API_KEY]
model: text-embedding-3-small
dimensions: 1536
docker: null
probe: openai_embedding_ping
bootstrap_step: null
emit_files: []
docs: |
  OpenAI's `text-embedding-3-small` as the default embedding provider for
  RAG recipes. 1536-dim output matches the recipe-side `vector_collections`
  defaults. Note: this is OpenAI for embeddings only — the primary LLM in
  this stack remains Anthropic Claude (`stack/llm-claude.md`). Separate
  vendors for separate jobs.
---

# Capability: embedding.openai

> First-run setup: shares the [`getting-started/anthropic.md`](../../getting-started/anthropic.md) flow plus the OpenAI API key. Vendor: https://platform.openai.com/docs/guides/embeddings.

**Used for:** Generating text embeddings for vector-DB ingestion and query-side encoding.

## Why pick this

`text-embedding-3-small` is the best-quality-per-dollar embedding model as of 2026, and 1536 dimensions matches what every recipe-side `vector_collections:` block defaults to. Cheap enough to use freely; fast enough that batch indexing is rarely the bottleneck.

The canonical stack uses Anthropic Claude for generation and OpenAI for embeddings — splitting vendors here trades a second credential for picking the best tool per job. Alternative impls swap embedding providers without affecting generation.

## Wiring

Capabilities of `kind: embedding` are resolved by the recipe's RAG layer when `capabilities[]` declares one. The scaffold wires the embedding client into the indexing step + the query encoder; no explicit recipe field beyond `capabilities: [embedding.openai]`.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `OPENAI_API_KEY` | *(prompted)* | OpenAI API key — stored via keyring |

## Probe

`openai_embedding_ping` calls `/v1/embeddings` with the literal string `"healthcheck"` and asserts a 1536-dim vector comes back. Run by `agent-scaffold doctor`.

## Dimensions

Pin `dimensions: 1536` end-to-end. Any `vector_db.*` capability the recipe uses must be configured with the same vector size in `bootstrap_config.vector_collections[].vector_size`.

## When to swap it

- **→ `embedding.openai-large`** — `text-embedding-3-large` for higher recall at 3× cost; bump vector_size to 3072.
- **→ `embedding.voyage-3`** — Voyage AI's 2026 model; competitive quality, different cost curve.
- **→ `embedding.local-bge`** — self-hosted BGE-M3 under TEI; for offline / compliance use.

## See also

- [`stack/llm-claude.md`](../../stack/llm-claude.md) — primary generation LLM (separate vendor).
- [`vector_db/qdrant.md`](../vector_db/qdrant.md) — typical paired vector store.
