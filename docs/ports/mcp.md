---
id: mcp
protocol: tools
required: false
cardinality: many
default: null
interface_version: "1.0"
kinds: [mcp]
adapter_home: capabilities
---

# MCP tool server — Port

Model-controlled tools exposed over the Model Context Protocol.

Adapters bind this port by declaring `implements: {port: mcp, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`. It realizes the kernel IR `protocol: tools` contract (see agent-blueprints `core/spec/ir.schema.json`).

