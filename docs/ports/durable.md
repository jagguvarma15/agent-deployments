---
id: durable
protocol: runtime
required: false
cardinality: one
default: null
interface_version: "1.0"
kinds: [durable]
adapter_home: capabilities
---

# Durable runtime — Port

Durable execution for crash-safe, long-running and resumable runs.

Adapters bind this port by declaring `implements: {port: durable, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`. It realizes the kernel IR `protocol: runtime` contract (see agent-blueprints `core/spec/ir.schema.json`).

