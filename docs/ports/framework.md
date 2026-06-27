---
id: framework
required: true
cardinality: one
default: null
interface_version: "1.0"
kinds: []
adapter_home: frameworks
---

# Agent framework — Port

The code framework the agent core is built on (LangGraph, Pydantic-AI, plain, ...).

Adapters bind this port by declaring `implements: {port: framework, interface_version: ...}` in their frontmatter, and advertise capability flags via `provides:`.

