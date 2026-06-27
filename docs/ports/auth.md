---
id: auth
required: false
cardinality: one
default: null
interface_version: "1.0"
kinds: [auth]
adapter_home: capabilities
---

# Auth — Port

Authentication and API-key bootstrap.

Adapters bind this port by declaring `implements: {port: auth, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`.

