---
id: core
required: true
cardinality: one
default: null
interface_version: "1.0"
kinds: [core]
adapter_home: capabilities
---

# Core scaffolding — Port

Always-present agent-core primitives (prompts, typed I/O, tool registry).

Adapters bind this port by declaring `implements: {port: core, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`.

