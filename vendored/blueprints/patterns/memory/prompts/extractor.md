---
role: extractor
pattern: memory
inputs:
  - {name: user_id, type: string, description: "Owner of the memories being extracted."}
  - {name: user_message, type: string, description: "The turn to extract durable facts from."}
  - {name: recent_context, type: array, description: "Last N turns for disambiguation; not stored."}
output_schema:
  type: object
  required: [new_entries]
  properties:
    new_entries:
      type: array
      items:
        type: object
        required: [content, kind]
        properties:
          content:
            type: string
            description: "Self-contained natural-language statement; readable without context."
          kind:
            type: string
            enum: [fact, preference, event, constraint]
            description: "Coarse category; drives downstream retrieval routing."
          confidence:
            type: ["number", "null"]
            minimum: 0
            maximum: 1
            description: "Optional 0..1 extractor self-confidence; entries below threshold may be discarded."
model_hint: haiku
estimated_tokens: 300
---

# Memory — extractor

Reads one user message and emits durable memories worth persisting. Haiku-class because the work is mostly entity / statement extraction.

## Prompt template

```text
You extract durable memories about a user from a single message. Skip ephemera.

User id: {{user_id}}

Recent context (for disambiguation only — do NOT extract from these):
{{recent_context}}

Current message:
{{user_message}}

Respond as a JSON object matching the schema. Rules:
- A "fact" is something objectively true ("works at Acme since 2024").
- A "preference" is a stated like/dislike ("prefers dark mode").
- An "event" is a notable thing that happened to the user ("got promoted last week").
- A "constraint" is a rule the assistant must respect ("never recommend airline X").
- Each "content" must read self-contained — a future retrieval will surface it without
  the surrounding message. Resolve pronouns and demonstratives.
- Return an empty array if the message has nothing durable. Don't fabricate memories
  to fill the response.
```

## Notes

- The hardest discipline is returning an empty array. Most user messages have zero durable memories — phatic acknowledgements, follow-up questions, ephemera. Eval suites must include negative examples (~50% of messages should extract nothing).
- `confidence` is optional but useful for cleanup batches — periodically purge entries below a threshold to keep recall precision high.
- Don't extract IDs, secrets, or PII into `content` — the storage layer should hash or redact those separately. This prompt sees free text; sanitization happens downstream.
