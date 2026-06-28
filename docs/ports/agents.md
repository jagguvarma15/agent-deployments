---
id: agents
protocol: agents
required: false
cardinality: many
default: null
interface_version: "1.0"
kinds: []
---

# Agent delegation — Port

Delegation to sub-agents (in-process) or remote A2A agents. Pattern-level; reserved.

Adapters bind this port by declaring `implements: {port: agents, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`. It realizes the kernel IR `protocol: agents` contract (see agent-blueprints `core/spec/ir.schema.json`).

