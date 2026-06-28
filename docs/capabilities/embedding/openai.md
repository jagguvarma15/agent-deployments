---
id: embedding.openai
kind: embedding
implements:
  port: embedding
  interface_version: "1.0"
layer: agent
provides: [text_embeddings]
env_vars: [OPENAI_API_KEY]
model: text-embedding-3-small
dimensions: 1536
docker: null
probe: openai_embedding_ping
bootstrap_step: null
provisioning_time: instant
cost_tier: per-call
est_tokens: 500
card:
  name: OpenAI Embeddings
  description: "OpenAI text-embedding-3-small (1536 dim) for RAG ingestion and query encoding."
  capabilities_provided: [text_embeddings]
  required_credentials: [OPENAI_API_KEY]
emit_files: []
docs: |
  OpenAI's `text-embedding-3-small` as the default embedding provider for
  RAG recipes. 1536-dim output matches recipe-side `vector_collections`
  defaults. Note: this is OpenAI for embeddings only — the primary LLM in
  this stack remains Anthropic Claude.
tags: [embeddings, openai, hosted]
when_to_load: "recipe declares embedding.openai"
verification:
  tier: T1
---

# Capability: embedding.openai

> First-run setup: shares the [`getting-started/anthropic.md`](../../getting-started/anthropic.md) flow plus the OpenAI API key. Vendor: https://platform.openai.com/docs/guides/embeddings.

**Used for:** Generating text embeddings for vector-DB ingestion and query-side encoding.

## Local setup

No container — the API is hosted. Add the OpenAI SDK to the generated project:

- Python: `openai`
- TypeScript: `openai`

## Wiring

Capabilities of `kind: embedding` are resolved by the recipe's RAG layer when `capabilities[]` declares one. The scaffold wires the embedding client into the indexing step + the query encoder; no explicit recipe field beyond `capabilities: [embedding.openai]`.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `OPENAI_API_KEY` | *(prompted)* | OpenAI API key — stored via keyring |

## Dimensions

Pin `dimensions: 1536` end-to-end. Any `vector_db.*` capability the recipe uses must be configured with the same vector size in `bootstrap_config.vector_collections[].vector_size`.

## Client integration

**Python (openai):**

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

# Single
resp = await client.embeddings.create(
    model="text-embedding-3-small",
    input="passage text",
)
embedding = resp.data[0].embedding  # 1536 floats

# Batch (up to 2048 inputs)
resp = await client.embeddings.create(
    model="text-embedding-3-small",
    input=["passage 1", "passage 2", "passage 3"],
)
embeddings = [d.embedding for d in resp.data]
```

**TypeScript (openai):**

```ts
import OpenAI from "openai";

const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY! });

const resp = await client.embeddings.create({
  model: "text-embedding-3-small",
  input: ["passage 1", "passage 2"],
});
const embeddings = resp.data.map((d) => d.embedding);
```

## Probe

`openai_embedding_ping` calls `/v1/embeddings` with the literal string `"healthcheck"` and asserts a 1536-dim vector comes back.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 Unauthorized` | Wrong key / wrong org | Recreate key in the right OpenAI org (Settings → API Keys) |
| Embeddings dimension mismatch with vector DB | Vector DB collection created at different dim | Drop + recreate collection at 1536; or override model dim via `dimensions=512` parameter |
| `429 Too Many Requests` | Tier rate limit | Add backoff (`tenacity`), or batch up to 2048 inputs per call |
| Token limit exceeded on long passages | `text-embedding-3-small` cap is 8191 tokens | Chunk passages to <8000 tokens before embedding |

## See also

- [`stack/llm-claude.md`](../../stack/llm-claude.md) — primary generation LLM (separate vendor)
- [`capabilities/vector_db/qdrant.md`](../vector_db/qdrant.md) — typical paired vector store
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
