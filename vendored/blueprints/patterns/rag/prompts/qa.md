---
role: qa
pattern: rag
inputs:
  - {name: question, type: string, description: "User's natural-language question."}
  - {name: retrieved, type: array, description: "List of {id, content, source} from the vector store, ranked by relevance."}
output_schema:
  type: object
  required: [text, citations, grounded]
  properties:
    text:
      type: string
      description: "The answer; cite sources inline by id."
    citations:
      type: array
      items: {type: string}
      description: "RetrievedDoc.id values the answer actually used."
    grounded:
      type: boolean
      description: "False when retrieval was insufficient and the answer would be speculative."
model_hint: sonnet
estimated_tokens: 700
---

# RAG — qa

Synthesizes a grounded answer from retrieved documents. Refuses (with `grounded: false`) when retrieval is too sparse or off-topic to answer responsibly.

## Prompt template

```text
You answer questions using only the provided documents. Cite every claim by document id.

Documents:
{{retrieved}}

Question: {{question}}

Respond as a JSON object matching the schema. Rules:
- Only use facts from the documents. Do not draw on outside knowledge.
- If the documents are insufficient or contradictory, set "grounded": false and explain what
  is missing in "text".
- Every id in "citations" must appear at least once in "text" (e.g. "[doc-12]"). Don't cite
  ids you didn't actually use.
```

## Notes

- The `grounded: false` exit is critical — without it the model learns to fabricate when retrieval misses. Run hallucination evals that include negative-control questions whose relevant docs are deliberately omitted.
- Truncate `retrieved` to the top-K (5–10) before injecting; pushing 50 docs costs tokens for no recall benefit at the synthesis step.
- Citation format (`[doc-12]` vs footnote-style) is a downstream-rendering concern; the prompt only requires inline ids that match `citations`.
