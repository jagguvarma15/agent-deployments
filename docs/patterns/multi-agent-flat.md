# Pattern: Multi-Agent Flat (Peer Collaboration)

**One-liner:** Multiple specialized agents collaborate as peers, each handling part of a task, without a central supervisor.

## When to use

- The task naturally splits into independent specialist domains (e.g., DevOps + Security + Database).
- Agents need to collaborate but no single agent should be "in charge."
- You want modular agent design where adding a new specialist doesn't change the others.
- Each agent has a distinct tool set and expertise.

## When NOT to use

- One agent can handle the task alone (simpler is better).
- Agents need strict coordination or sequencing (use Hierarchical or Plan-and-Execute).
- The number of agents is large (>5) — coordination overhead grows. Use hierarchical instead.

## Core flow

```
User task
    |
    v
  [Task distribution] ──> split across agents
    |
    ├──> [Agent A: DevOps] ──> findings
    ├──> [Agent B: Security] ──> findings
    └──> [Agent C: Database] ──> findings
                                    |
                                    v
                              [Aggregation]
                                    |
                                    v
                              Combined report
```

### Variants

- **Independent execution:** Each agent works on its piece independently, results merged at the end. No inter-agent communication.
- **Round-robin discussion:** Agents take turns adding to a shared context. Each sees what prior agents said.
- **Debate/critique:** Agents review each other's outputs and provide feedback. Converges through iteration.
- **Handoff:** Agents pass work to each other when they encounter something outside their expertise.

## Key components

- **Crew/Team:** The container that holds the set of agents and defines how they interact (parallel, sequential, round-robin).
- **Agent:** An LLM with a specialized system prompt and tool set. Each agent has a distinct role.
- **Task:** A unit of work assigned to one or more agents. Has a description, expected output, and optionally a designated agent.
- **Communication protocol:** How agents share information — shared state, message passing, or output chaining.
- **Aggregator:** Merges individual agent outputs into a cohesive result.

## Common pitfalls

- **Role overlap:** Two agents covering similar ground produces redundant or contradictory output. Define clear boundaries.
- **No aggregation strategy:** Individual agent outputs dumped together aren't useful. Design the merge step.
- **Excessive communication:** Agents chatting with each other burns tokens and adds latency. Minimize inter-agent messages.
- **Lowest common denominator:** The final output quality is limited by the weakest agent. Each specialist needs to be good at its job.
- **Coordination failure:** Without a supervisor, no one resolves disagreements between agents. Have a tie-breaking mechanism.

## Framework fit

| Framework | Native support | Notes |
|-----------|----------------|-------|
| CrewAI | Purpose-built — `Crew`, `Agent`, `Task` abstractions | Best fit for flat multi-agent |
| LangGraph | Multiple sub-graphs composed in a parent graph | More manual but more control |
| Mastra | Multi-agent workflows with agent handoffs | TS-native option |
| Pydantic AI | Multiple agents orchestrated manually | Works but no built-in multi-agent |
| Vercel AI SDK | Manual orchestration | No multi-agent primitives |

## Reference implementations

- [recipes/ops-crew.md](../recipes/ops-crew.md) — DevOps/Security/Database ops crew with CrewAI (skeleton)
