# Pattern: Routing + Tool Use

**One-liner:** Classify the user's intent, then route to a specialized handler (agent or tool) for that intent.

## When to use

- Incoming requests fall into distinct categories with different handling logic (e.g., billing vs. technical support).
- You want to use a cheap/fast model for classification and a capable model for handling.
- Each category needs different tools, system prompts, or guardrails.
- You need clear audit trails showing why a request was routed a specific way.

## When NOT to use

- There's only one type of request (just use a single agent with tools).
- The categories overlap heavily and routing would be wrong half the time.
- The task requires multi-step reasoning across categories (use ReAct or Multi-Agent).

## Core flow

```
User message
    |
    v
  [Classifier] ──> intent + confidence
    |
    ├── billing ──> [Billing Specialist] ──> (Stripe tool)
    ├── technical ──> [Technical Specialist] ──> (KB search tool)
    ├── account ──> [Account Specialist] ──> (KB search tool)
    └── general ──> [General Specialist] ──> (no tools)
    |
    v
  Response
```

### Variants

- **Single-hop routing:** Classify once, route once. Simple and fast.
- **Cascading routers:** First router picks a domain, second router picks a sub-category within that domain.
- **Confidence-gated routing:** If classifier confidence is below threshold, fall back to a general handler or ask for clarification.
- **Tool-only routing:** Instead of separate agents, the classifier picks which tool to invoke. Lighter-weight.

## Key components

- **Classifier:** An LLM (often smaller/cheaper) that maps input to an intent. Returns structured output: intent enum + confidence score + reasoning.
- **Specialist agents:** One per intent category, each with its own system prompt and tool set. Specialists are isolated — a billing agent can't accidentally call the KB search tool.
- **Router:** Dispatches to the correct specialist based on classification. In code, this is typically a match/switch on the intent enum.
- **Fallback handler:** Catches low-confidence classifications or unknown intents.

## Common pitfalls

- **Overlapping intents:** "I can't log in to pay my bill" is both account and billing. Define clear boundaries or allow multi-label classification with priority.
- **Classifier drift:** As your product changes, new intents emerge. Monitor classification accuracy and retrain/update prompts.
- **Over-routing:** Too many intent categories makes classification unreliable. Start with 3-5 categories.
- **Missing fallback:** Without a fallback, unclassifiable messages get random routing. Always have a general handler.
- **Specialist without tools:** If a specialist can't actually do anything (no tools, no data access), it's just a differently-prompted chatbot. Make sure specialists have real capabilities.

## Framework fit

| Framework | Native support | Notes |
|-----------|----------------|-------|
| Pydantic AI | `result_type=ClassificationResult` for structured classification, separate `Agent` per specialist | Natural fit — typed outputs + tool isolation |
| LangGraph | Conditional edges from classifier node to specialist nodes | Works well but verbose for simple routing |
| Mastra | Agent with `tools` per specialist, manual routing | Clean, no extra abstraction needed |
| Vercel AI SDK | `generateObject()` for classification, `generateText()` per specialist | Lightweight TS option |
| CrewAI | Not idiomatic — CrewAI is designed for collaboration, not routing | Use a different framework |

## Reference implementations

- [recipes/customer-support-triage.md](../recipes/customer-support-triage.md) — Intent classification → specialist routing (Pydantic AI / Mastra)
