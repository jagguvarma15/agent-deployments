# Primitives

Building blocks the agent uses orthogonally to any pattern. Picking primitives is the **second** of three decisions when designing an agent (pattern → primitives → modifiers).

Primitives don't change the agent's flow shape — they describe *what the agent has access to* during that flow. Same primitive (memory, say) composes with every pattern (ReAct, RAG, Multi-Agent, …) without changing the pattern's reasoning shape.

For the picker question per primitive ("Does the agent need tools? memory? skills?"), see [`../foundations/choosing-a-pattern.md`](../foundations/choosing-a-pattern.md#step-2--pick-primitives-zero-or-more).

<!-- AUTO:cohort-table cohort=primitives style=tiers base=../ -->
| Pattern | What It Does | Evolves From | Overview | Design | Implementation |
|---|---|---|---|---|---|
| **Memory** | Persistent state across sessions: short-term, long-term, and semantic memory. | Prompt Chaining | [overview](../primitives/memory/overview.md) | [design](../primitives/memory/design.md) | [impl](../primitives/memory/implementation.md) |
| **Skills** | File-based, agent-discovered procedural modules. Cheap to ship many; loaded on demand at runtime. | Tool Use | [overview](../primitives/skills/overview.md) | [design](../primitives/skills/design.md) | [impl](../primitives/skills/implementation.md) |
| **Sub-agents** | Named, role-scoped agent instances spawned by a parent for delimited tasks; each has its own context window, tool grants, and (optionally) model. | Tool Use | [overview](../primitives/sub_agents/overview.md) | [design](../primitives/sub_agents/design.md) | [impl](../primitives/sub_agents/implementation.md) |
| **Tool Use** | Structured function calling with schema-validated tool dispatch. | Prompt Chaining | [overview](../primitives/tool_use/overview.md) | [design](../primitives/tool_use/design.md) | [impl](../primitives/tool_use/implementation.md) |
<!-- /AUTO -->

## Authoring a new primitive

See [`../meta/HOW_TO_ADD_AN_ENTRY.md`](../meta/HOW_TO_ADD_AN_ENTRY.md#adding-a-primitive). The contract is the same as patterns and modifiers: drop a directory + metadata.json + tier files, run the generators.
