---
id: obs
concern: observability
required: false
cardinality: many
default: obs.langfuse
interface_version: "1.0"
kinds: [obs]
adapter_home: capabilities
---

# Observability — Port

Tracing and metrics backend for agent runs (OpenTelemetry GenAI shape).

Adapters bind this port by declaring `implements: {port: obs, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`. It realizes the kernel IR `concern: observability` contract (see agent-blueprints `core/spec/ir.schema.json`).

