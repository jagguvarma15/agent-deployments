---
id: live_data
protocol: tools
required: false
cardinality: many
default: null
interface_version: "1.0"
kinds: [live_data]
adapter_home: capabilities
---

# Live-data tool — Port

Real-time data sources the agent can query as tools.

Adapters bind this port by declaring `implements: {port: live_data, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`. It realizes the kernel IR `protocol: tools` contract (see agent-blueprints `core/spec/ir.schema.json`).

