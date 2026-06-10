---
role: chat
pattern: memory
inputs:
  - {name: user_id, type: string, description: "Owner of the memories being consulted."}
  - {name: user_message, type: string, description: "Current turn the assistant responds to."}
  - {name: recall, type: object, description: "Retrieved memories: {query, entries: [{id, content, kind}], scores}."}
  - {name: conversation_history, type: array, description: "Recent message turns for short-term context."}
output_schema:
  type: object
  required: [response, refers_to_memory_ids]
  properties:
    response:
      type: string
      description: "The assistant's reply."
    refers_to_memory_ids:
      type: array
      items: {type: string}
      description: "Memory ids actually used in the response; drives last_used_at updates."
model_hint: sonnet
estimated_tokens: 700
---

# Memory — chat

The user-facing turn. Has access to retrieved long-term memories plus recent conversation. Reports which memory ids it actually used so the storage layer can update `last_used_at` for eviction-LRU.

## Prompt template

```text
You are a conversational assistant with access to durable memories about this user.

Relevant memories:
{{recall.entries}}

Recent conversation:
{{conversation_history}}

User: {{user_message}}

Respond as a JSON object matching the schema. Rules:
- Reference memories naturally — don't quote ids in the response text. The ids belong only
  in "refers_to_memory_ids".
- If a memory contradicts what the user just said, prefer the user's current statement and
  treat the memory as outdated (the storage layer handles correction in a separate turn).
- Only list ids in "refers_to_memory_ids" that you actually used. Including unused ids
  pollutes the eviction signal.
- If "recall.entries" is empty, respond from conversation history alone — don't apologize
  for lack of memory.
```

## Notes

- The `refers_to_memory_ids` honesty contract is what keeps the memory store useful long-term. Eval suites should fail responses that contradict listed ids (used-but-not-applied) or omit ids referenced obliquely in the text (applied-but-not-listed).
- Don't run extractor and chat from the same call — separate prompts isolate failure modes. The extractor's mistakes shouldn't degrade chat quality.
- For users with thousands of memories, `recall.entries` should be capped at 10–15 and re-ranked by a lightweight scorer before injection.
