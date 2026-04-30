# Pattern: ReAct (Reason + Act)

**One-liner:** The agent iterates through a think → act → observe loop, choosing tools at each step until it can answer.

## When to use

- The task requires multi-step reasoning with external information (search, APIs, databases).
- You can't predict upfront which tools the agent will need or in what order.
- The agent needs to adapt its strategy based on intermediate results.
- You want an auditable trace of the agent's reasoning at each step.

## When NOT to use

- The task is a single classification or generation (no tools needed — just prompt).
- The workflow is a fixed sequence of steps (use Prompt Chaining instead).
- You need guaranteed execution order or deterministic outputs (ReAct is inherently non-deterministic).
- Latency budget is tight — each loop iteration is an LLM call.

## Core flow

```
User question
    |
    v
  [Reason] ──> "I need to search for X"
    |
    v
  [Act] ──> call tool(search, query="X")
    |
    v
  [Observe] ──> tool returns results
    |
    v
  [Reason] ──> "Now I need to look up Y"
    |            ... (loop until done)
    v
  [Final Answer]
```

### Loop termination

The LLM decides when it has enough information to answer. Most frameworks enforce a `max_steps` limit to prevent runaway loops. In this repo, the default is 5 steps.

### Variants

- **Vanilla ReAct:** Single agent, flat tool list. The most common variant.
- **ReAct + reflection:** After each observation, a separate prompt critiques whether the approach is working.
- **ReAct + planning:** The agent first writes a brief plan, then executes via ReAct. Hybrid with Plan-and-Execute.

## Key components

- **Reasoner:** The LLM generating thoughts about what to do next. The system prompt defines its persona and available tools.
- **Tool executor:** Runs the chosen tool and returns results. In Pydantic AI, tools are decorated functions. In LangGraph, `ToolNode` handles this.
- **Observation parser:** Feeds tool results back into the next reasoning step as context.
- **Step limiter:** Prevents infinite loops. Configurable via `max_steps` or equivalent.

## Common pitfalls

- **Tool description quality:** Vague tool descriptions cause the agent to pick wrong tools. Be precise about what each tool does, its inputs, and output format.
- **Too many tools:** More than ~10 tools degrades selection accuracy. Group related tools or use a routing layer.
- **No step limit:** Without `max_steps`, the agent can loop indefinitely on hard questions. Always set a cap.
- **Expensive tool calls in loops:** If a tool hits a paid API, each loop iteration costs money. Consider caching or rate-limiting tool calls.
- **Hallucinated tool names:** The agent may try to call tools that don't exist. Ensure your framework validates tool names before execution.

## Framework fit

| Framework | Native support | Notes |
|-----------|----------------|-------|
| LangGraph | `create_react_agent()` — purpose-built | Canonical implementation with full state management |
| Pydantic AI | `Agent` with `@tool` decorators — built-in loop | Clean DX, auto-manages the reason/act/observe cycle |
| Mastra | `Agent` with `tools` array — built-in loop | TS-native, similar ergonomics to Pydantic AI |
| Vercel AI SDK | `generateText()` with `tools` + `maxSteps` | Lightweight, good for simple ReAct |
| CrewAI | Agent with tools — uses ReAct internally | Works but less control over the loop |

## Reference implementations

- [recipes/research-assistant.md](../recipes/research-assistant.md) — ReAct research agent with web search (Pydantic AI / Mastra)
