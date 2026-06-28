---
id: memory_store
protocol: memory
required: false
cardinality: one
default: null
interface_version: "1.0"
kinds: [memory_store]
adapter_home: capabilities
---

# Memory store — Port

Long-term / episodic / semantic agent memory behind a managed service.

Adapters bind this port by declaring `implements: {port: memory_store, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`. It realizes the kernel IR `protocol: memory` contract (see agent-blueprints `core/spec/ir.schema.json`).

