---
id: rerank
protocol: model
required: false
cardinality: one
default: null
interface_version: "1.0"
kinds: [rerank]
adapter_home: capabilities
---

# Reranker — Port

Re-scores retrieved candidates for relevance before generation.

Adapters bind this port by declaring `implements: {port: rerank, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`. It realizes the kernel IR `protocol: model` contract (see agent-blueprints `core/spec/ir.schema.json`).

