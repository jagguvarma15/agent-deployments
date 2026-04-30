# Pattern: Multi-Agent Hierarchical (Supervisor + Workers)

**One-liner:** A supervisor agent delegates sub-tasks to specialized worker agents, coordinates their outputs, and decides when the job is done.

## When to use

- The task is complex and decomposes into sub-tasks that require different specializations.
- You need centralized coordination — someone to decide what happens next based on intermediate results.
- Sub-agents may need to be called multiple times or in different orders depending on results.
- You want a clear chain of command for audit and debugging purposes.

## When NOT to use

- The task doesn't require multiple specializations (use a single agent with tools).
- All sub-tasks are independent with no coordination needed (use Parallel Calls or Flat Multi-Agent).
- The number of sub-agents is small (2) and the interaction is simple (just use Routing).

## Core flow

```
User task
    |
    v
  [Supervisor] ──> "I need Agent A to do X first"
    |
    v
  [Agent A: Researcher] ──> results
    |
    v
  [Supervisor] ──> "Now I need Agent B to do Y with A's results"
    |
    v
  [Agent B: Writer] ──> draft
    |
    v
  [Supervisor] ──> "Agent C should review this"
    |
    v
  [Agent C: Reviewer] ──> feedback
    |
    v
  [Supervisor] ──> "Done" or "Agent B, revise based on feedback"
    |
    v
  Final output
```

### Variants

- **Single-level hierarchy:** One supervisor, N workers. Most common.
- **Multi-level hierarchy:** Supervisor → sub-supervisors → workers. For very complex tasks.
- **Supervisor with self-delegation:** The supervisor can also do work itself, not just delegate.
- **Dynamic team:** The supervisor can spawn new workers as needed based on the task.

## Key components

- **Supervisor agent:** The orchestrator. Decides which worker to call, with what input, and when to stop. Has access to all worker agent descriptions but not their tools directly.
- **Worker agents:** Specialized agents with their own system prompts and tools. Each handles one domain.
- **Delegation protocol:** How the supervisor invokes workers — typically as tool calls where each worker is a "tool" the supervisor can call.
- **State manager:** Tracks what's been done, what's pending, and intermediate results. LangGraph's state graph is ideal.
- **Termination logic:** The supervisor decides when the task is complete. Can be explicit ("all sub-tasks done") or LLM-judged.

## Common pitfalls

- **Supervisor bottleneck:** Every interaction goes through the supervisor, adding latency. For independent sub-tasks, let workers run in parallel.
- **Over-delegation:** The supervisor breaks the task into too many tiny sub-tasks. Give it examples of good delegation granularity.
- **Lost context:** Each worker only sees its sub-task, not the full picture. The supervisor must provide enough context in each delegation.
- **Supervisor hallucination:** The supervisor claims a worker returned results it didn't. Validate worker outputs in state.
- **Worker scope creep:** A worker tries to do work outside its specialty. Keep worker system prompts narrowly focused.

## Framework fit

| Framework | Native support | Notes |
|-----------|----------------|-------|
| LangGraph | `langgraph-supervisor` package — purpose-built supervisor pattern | Best fit — each worker is a compiled sub-graph |
| CrewAI | Hierarchical process mode with `manager_agent` | Built-in but less flexible than LangGraph |
| Mastra | Agent workflows with delegation | TS-native, manual but flexible |
| Pydantic AI | Manual orchestration — supervisor agent with workers as tools | Works but you build the coordination |
| Vercel AI SDK | Manual orchestration | No built-in hierarchy |

## Reference implementations

- [recipes/hierarchical-agent.md](../recipes/hierarchical-agent.md) — Hierarchical multi-agent with LangGraph supervisor (skeleton)
