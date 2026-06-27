---
id: model
protocol: model
required: true
cardinality: one
default: null
interface_version: "1.0"
kinds: []
adapter_home: stack
---

# Model (LLM) — Port

The reasoning LLM the agent calls each step.

Adapters bind this port by declaring `implements: {port: model, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`. It realizes the kernel IR `protocol: model` contract (see agent-blueprints `core/spec/ir.schema.json`).

