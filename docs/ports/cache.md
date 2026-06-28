---
id: cache
protocol: memory
required: false
cardinality: one
default: null
interface_version: "1.0"
kinds: [cache]
adapter_home: capabilities
---

# Cache — Port

Low-latency key/value cache and session store.

Adapters bind this port by declaring `implements: {port: cache, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`. It realizes the kernel IR `protocol: memory` contract (see agent-blueprints `core/spec/ir.schema.json`).

