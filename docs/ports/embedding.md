---
id: embedding
protocol: model
required: false
cardinality: one
default: null
interface_version: "1.0"
kinds: [embedding]
adapter_home: capabilities
---

# Embedding model — Port

Turns text into vectors for retrieval and semantic memory.

Adapters bind this port by declaring `implements: {port: embedding, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`. It realizes the kernel IR `protocol: model` contract (see agent-blueprints `core/spec/ir.schema.json`).

