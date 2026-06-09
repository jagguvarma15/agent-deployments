---
role: interrupt-formatter
pattern: human-in-the-loop
inputs:
  - {name: raw_interrupt, type: object, description: "Interrupt the agent emitted: {kind, prompt, options, context}."}
  - {name: redaction_rules, type: array, description: "Patterns/fields to redact from context before showing the human."}
  - {name: ui_constraints, type: object, description: "Channel-specific limits (max prompt length, max options, formatting hints)."}
output_schema:
  type: object
  required: [prompt, kind]
  properties:
    prompt:
      type: string
      description: "Human-readable, channel-appropriate prompt text."
    kind:
      type: string
      enum: [approval, clarification, selection, input]
      description: "Echoes raw_interrupt.kind; included so UI rendering can branch."
    options:
      type: array
      items: {type: string}
      description: "Final option labels for selection/approval; empty for input."
    safe_context:
      type: object
      description: "Context object with redaction_rules applied; safe to render in the UI."
    severity:
      type: ["string", "null"]
      enum: [info, warning, danger, null]
      description: "Optional UI severity hint; danger triggers extra confirmation steps."
model_hint: haiku
estimated_tokens: 300
---

# Human-in-the-Loop — interrupt-formatter

Polishes a raw Interrupt from the agent into something safe and clear to show the human. Applies redaction, length limits, and severity hints. Stateless — runs once per interrupt.

## Prompt template

```text
You convert a raw agent interrupt into a human-facing prompt.

Raw interrupt:
{{raw_interrupt}}

Redaction rules (apply to context before rendering):
{{redaction_rules}}

UI constraints (channel-specific):
{{ui_constraints}}

Respond as a JSON object matching the schema. Rules:
- Rewrite "raw_interrupt.prompt" to be clear, concise, and within ui_constraints
  (length, formatting). Don't add information the agent didn't include — only
  reformat.
- Apply EVERY redaction_rule to context. Missing a redaction is a privacy bug.
- "options" must match raw_interrupt.options 1:1 in order, but labels can be polished
  ("Yes, refund" instead of "yes_refund").
- "severity": "danger" for irreversible actions (deletes, payments, account changes).
  "warning" for high-impact reversible actions. "info" for clarifications. null when
  the kind itself implies severity (approval → warning, others → info).
```

## Notes

- This prompt is intentionally Haiku — it's a transform, not a decision. Putting Sonnet here costs money for no benefit.
- The redaction discipline is the privacy boundary. If `redaction_rules` is empty, fall back to a default deny-list (passwords, tokens, PII) — empty rules should not mean "show everything".
- `safe_context` is what the UI renders alongside the prompt for the human to decide on. Keep it small; if context is large, the agent should have summarized before emitting the interrupt.
