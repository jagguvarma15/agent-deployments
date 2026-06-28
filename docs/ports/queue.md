---
id: queue
protocol: runtime
required: false
cardinality: many
default: null
interface_version: "1.0"
kinds: [queue]
adapter_home: capabilities
---

# Queue / stream — Port

Async messaging for event-driven and worker topologies.

Adapters bind this port by declaring `implements: {port: queue, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`. It realizes the kernel IR `protocol: runtime` contract (see agent-blueprints `core/spec/ir.schema.json`).

