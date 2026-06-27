---
id: relational
protocol: memory
required: false
cardinality: one
default: null
interface_version: "1.0"
kinds: [relational]
adapter_home: capabilities
---

# Relational store — Port

Durable relational persistence (state, checkpoints, app data).

Adapters bind this port by declaring `implements: {port: relational, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`. It realizes the kernel IR `protocol: memory` contract (see agent-blueprints `core/spec/ir.schema.json`).

