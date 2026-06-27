---
id: host
required: false
cardinality: one
default: null
interface_version: "1.0"
kinds: [host]
adapter_home: capabilities
---

# Deploy host — Port

The deploy target (container, serverless, or managed PaaS).

Adapters bind this port by declaring `implements: {port: host, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`.

