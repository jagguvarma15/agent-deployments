---
id: frontend
required: false
cardinality: one
default: null
interface_version: "1.0"
kinds: [frontend]
adapter_home: capabilities
---

# Frontend — Port

An optional chat or UI surface for the agent.

Adapters bind this port by declaring `implements: {port: frontend, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`.

