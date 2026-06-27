---
id: vector_db
protocol: memory
required: false
cardinality: one
default: null
interface_version: "1.0"
kinds: [vector_db]
adapter_home: capabilities
---

# Vector store — Port

Vector storage and similarity search for retrieval and semantic memory.

Adapters bind this port by declaring `implements: {port: vector_db, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`. It realizes the kernel IR `protocol: memory` contract (see agent-blueprints `core/spec/ir.schema.json`).

