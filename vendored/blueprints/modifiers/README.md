# Modifiers

Transformations layered on a pattern. Picking modifiers is the **third** of three decisions when designing an agent (pattern → primitives → modifiers).

Modifiers don't change the pattern's reasoning shape — they wrap a pattern with a concern like human approval, audit logging, dual-LLM filtering. Each modifier's `appliesTo` declares which patterns it can wrap (or `[any]` for universal modifiers).

For the picker question per modifier, see [`../foundations/choosing-a-pattern.md`](../foundations/choosing-a-pattern.md#step-3--pick-modifiers-zero-or-more).

<!-- AUTO:cohort-table cohort=modifiers style=tiers base=../ -->
| Pattern | What It Does | Evolves From | Overview | Design | Implementation |
|---|---|---|---|---|---|
| **Guardrails** | Layered input / tool / output policy checks plus a dual-LLM split that breaks the indirect-prompt-injection path. | Tool Use | [overview](../modifiers/guardrails/overview.md) | [design](../modifiers/guardrails/design.md) | [impl](../modifiers/guardrails/implementation.md) |
| **Human in the Loop** | Agent proposes an action; a human approves, denies, or modifies before the action commits. | Tool Use | [overview](../modifiers/human_in_the_loop/overview.md) | [design](../modifiers/human_in_the_loop/design.md) | [impl](../modifiers/human_in_the_loop/implementation.md) |
<!-- /AUTO -->

## Authoring a new modifier

See [`../meta/HOW_TO_ADD_AN_ENTRY.md`](../meta/HOW_TO_ADD_AN_ENTRY.md#adding-a-modifier). The contract is the same as patterns and primitives: drop a directory + metadata.json + tier files, run the generators.
