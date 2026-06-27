---
id: guardrail
concern: guardrails
required: false
cardinality: many
default: null
interface_version: "1.0"
kinds: [guardrail]
adapter_home: capabilities
---

# Guardrail — Port

Layered input / tool / output policy checks and injection defenses.

Adapters bind this port by declaring `implements: {port: guardrail, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`. It realizes the kernel IR `concern: guardrails` contract (see agent-blueprints `core/spec/ir.schema.json`).

