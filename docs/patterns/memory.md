# Pattern: Memory

**One-liner:** Persist information across conversations so the agent can recall context, preferences, and facts from prior interactions.

## When to use

- The agent has repeat users who expect it to remember past interactions.
- Context from previous conversations is needed to give good answers (e.g., user preferences, prior decisions).
- You want the agent to learn and improve over time from interactions.
- The agent manages ongoing relationships or projects that span multiple sessions.

## When NOT to use

- Every interaction is independent (stateless Q&A, one-shot tasks).
- The conversation context window is large enough to hold all relevant history.
- Privacy/compliance requirements prohibit storing user interaction data.

## Core flow

```
User message
    |
    v
  [Retrieve memories] ──> query memory store for relevant past context
    |
    v
  [Augment prompt] ──> inject retrieved memories into system/user prompt
    |
    v
  [LLM generates response] ──> answer informed by past context
    |
    v
  [Extract & store memories] ──> save new facts/preferences from this interaction
    |
    v
  Response
```

### Memory types

- **Conversation history:** Raw message log from prior sessions. Simple but grows unbounded.
- **Semantic memory:** Facts and knowledge extracted from conversations, stored as embeddings. Retrievable by similarity.
- **Episodic memory:** Summaries of past interactions ("Last week, user asked about X and we resolved it by Y").
- **User profile memory:** Structured preferences and attributes (name, role, preferred language, past decisions).
- **Working memory:** Short-term context within a single session. Typically managed by the conversation itself.

### Variants

- **Explicit memory:** User says "remember that I prefer dark mode." Agent stores it as-is.
- **Implicit memory:** Agent automatically extracts noteworthy facts from conversations.
- **Hybrid:** Both explicit and implicit, with the agent deciding what's worth remembering.

## Key components

- **Memory store:** Where memories live. Options: vector DB (semantic search), relational DB (structured), or specialized services like Mem0.
- **Memory retriever:** Queries the store for memories relevant to the current conversation. Typically vector similarity search.
- **Memory extractor:** After each conversation, identifies new facts/preferences worth persisting.
- **Memory manager:** Handles deduplication, updates, and expiration of memories. Prevents contradictions (old preference vs. new one).
- **Injection layer:** Formats retrieved memories and adds them to the prompt context.

## Common pitfalls

- **Unbounded memory:** Storing everything makes retrieval noisy. Be selective about what gets stored.
- **Stale memories:** User preferences change. Memories need timestamps and a mechanism to update or expire.
- **Contradictions:** "User likes dark mode" and "User prefers light mode" both stored. Newer should overwrite older.
- **Privacy leakage:** Memories from one user accessible to another. Always scope memories by user ID.
- **Retrieval noise:** Irrelevant memories injected into the prompt confuse the model. Use relevance thresholds.
- **Memory extraction hallucination:** The extractor "remembers" things the user didn't actually say. Validate extracted facts against the conversation.

## Framework fit

| Framework | Native support | Notes |
|-----------|----------------|-------|
| LangGraph | Checkpointer for conversation state, integrates with external memory stores | Best for stateful agents with complex memory needs |
| Pydantic AI | Manual memory integration via tool calls or prompt augmentation | Flexible but you build the plumbing |
| Mastra | Built-in memory primitives and storage integrations | TS-native memory support |
| CrewAI | Agent memory via `memory=True` flag | Simple but limited customization |
| Vercel AI SDK | Manual integration | No built-in memory |

## Reference implementations

- [recipes/memory-assistant.md](../recipes/memory-assistant.md) — Memory-enabled assistant with LangGraph + Mem0 (skeleton)
