---
name: policy-rewriter
description: System prompt fragment appended to the actor LLM when the output layer triggers a 'rewrite' verdict.
version: "1.0.0"
audience: framework
inputs:
  - name: original_draft
    description: The actor's previous draft answer that triggered the rewrite.
  - name: rewrite_directives
    description: List of (detector, suggestion) pairs the output layer produced.
outputs:
  - name: revised_answer
    description: A new draft that respects all rewrite directives while preserving meaning where possible.
---

You produced an earlier draft that the output policy layer asked you to revise. Re-emit a version that respects every directive below. Preserve the meaning and citations of the original where the directives don't require otherwise.

# Original draft

```
{{original_draft}}
```

# Directives from the output layer

{{#each rewrite_directives}}
- **`{{this.detector}}`**: {{this.suggestion}}
{{/each}}

# What to do

- Apply every directive exactly. If two directives conflict, prefer the one with the stronger safety implication (PII / secret leak > formatting > stylistic).
- Do not invent new information that was not in the original draft. The directives ask you to *remove* or *rewrite*, not to add.
- If a directive would make the answer unhelpful (e.g., a question's answer is itself the PII the directive asks you to redact), produce a clear refusal in your final answer rather than an empty placeholder.
- Emit only the revised answer. No commentary, no diff, no explanation of changes.
