---
id: eval
concern: eval
required: false
cardinality: one
default: null
interface_version: "1.0"
kinds: [eval]
adapter_home: capabilities
---

# Eval harness — Port

Offline and online evaluation of agent quality.

Adapters bind this port by declaring `implements: {port: eval, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`. It realizes the kernel IR `concern: eval` contract (see agent-blueprints `core/spec/ir.schema.json`).

