---
id: api_layer
required: true
cardinality: one
default: null
interface_version: "1.0"
kinds: []
adapter_home: stack
---

# API layer — Port

The HTTP / serving layer that exposes the agent.

Adapters bind this port by declaring `implements: {port: api_layer, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`.

