# Patterns

Architecture patterns for AI agents. Each file answers: **"What shape does my agent take?"**

| Pattern | One-liner | Best framework fit |
|---------|-----------|-------------------|
| [RAG](rag.md) | Ground answers in retrieved documents | LangGraph, Pydantic AI |
| [ReAct](react.md) | Think → act → observe loop with tools | LangGraph, Pydantic AI |
| [Routing + Tool Use](routing-tool-use.md) | Classify intent, route to specialist | Pydantic AI |
| [Prompt Chaining](prompt-chaining.md) | Fixed sequence of LLM calls | Pydantic AI, Vercel AI SDK |
| [Plan, Execute, Reflect](plan-execute-reflect.md) | Plan steps, execute, self-correct | LangGraph |
| [Parallel Calls](parallel-calls.md) | Fan-out / fan-in concurrent execution | Pydantic AI, Vercel AI SDK |
| [Memory](memory.md) | Persist context across conversations | LangGraph |
| [Multi-Agent Flat](multi-agent-flat.md) | Peer agents collaborating | CrewAI |
| [Multi-Agent Hierarchical](multi-agent-hierarchical.md) | Supervisor delegates to workers | LangGraph |

## How to pick a pattern

1. **Single task, no tools needed?** → Just prompt the model directly. No pattern needed.
2. **Need external data but fixed flow?** → [RAG](rag.md) or [Prompt Chaining](prompt-chaining.md)
3. **Need tools, unknown sequence?** → [ReAct](react.md)
4. **Multiple request types?** → [Routing + Tool Use](routing-tool-use.md)
5. **Complex task needing self-correction?** → [Plan, Execute, Reflect](plan-execute-reflect.md)
6. **N independent sub-tasks?** → [Parallel Calls](parallel-calls.md)
7. **Need cross-session context?** → [Memory](memory.md)
8. **Multiple specialists needed?** → [Multi-Agent Flat](multi-agent-flat.md) or [Hierarchical](multi-agent-hierarchical.md)
