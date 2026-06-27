---
id: sandbox
protocol: runtime
required: false
cardinality: one
default: null
interface_version: "1.0"
kinds: [sandbox]
adapter_home: capabilities
---

# Code sandbox — Port

Isolated execution for agent-generated code and risky tools.

Adapters bind this port by declaring `implements: {port: sandbox, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`. It realizes the kernel IR `protocol: runtime` contract (see agent-blueprints `core/spec/ir.schema.json`).

