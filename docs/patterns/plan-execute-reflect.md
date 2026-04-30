# Pattern: Plan, Execute, Reflect

**One-liner:** The agent creates a plan of steps, executes them one by one, then reflects on results to decide if re-planning is needed.

## When to use

- The task is complex enough that jumping straight to execution would miss steps or go off track.
- You want the agent to be self-correcting — detecting when a step failed and adapting.
- The task has a verifiable goal (code review: "all issues found"; research: "question answered").
- You need an auditable trace: plan → what was done → what was learned → revised plan.

## When NOT to use

- The task is simple enough for a single LLM call or a fixed pipeline (use Prompt Chaining).
- There's no way to evaluate whether a step succeeded (reflection has nothing to work with).
- Latency is critical — the plan/reflect overhead adds 2+ extra LLM calls per cycle.

## Core flow

```
User task
    |
    v
  [Planner] ──> step list (ordered, with dependencies)
    |
    v
  [Executor] ──> execute step 1 ──> result
    |                    |
    |                    v
    |             [Reflector] ──> "step succeeded" / "step failed, because..."
    |                    |
    |         ┌──────────┴──────────┐
    |         v                     v
    |    continue to             [Re-planner] ──> revised steps
    |    step 2                     |
    |         |                     v
    |         └─────────────────> next step
    |                    ...
    v
  Final output (after all steps pass reflection)
```

### Variants

- **Plan-Execute (no reflection):** Simpler version — plan once, execute all steps, return results. Good when steps are unlikely to fail.
- **Plan-Execute-Reflect:** Full version with a reflection step after each execution. Re-plans if reflection identifies problems.
- **Iterative deepening:** Start with a coarse plan, execute, reflect, then create more detailed sub-plans for steps that need it.

## Key components

- **Planner:** An LLM call that takes the task description and produces a structured step list. Each step has: description, expected output, success criteria.
- **Executor:** Runs one step at a time. May use tools (search, code execution, API calls) to complete each step.
- **Reflector:** Evaluates the executor's output against the step's success criteria. Returns pass/fail + reasoning.
- **Re-planner:** If reflection fails, takes the original plan + what happened + what went wrong, and produces a revised plan.
- **State store:** Holds the plan, completed steps, and their results. LangGraph's checkpointer is ideal for this.

## Common pitfalls

- **Over-planning:** The planner produces 15 steps for a task that needs 3. Constrain the planner with max steps or examples of good plans.
- **Reflection hallucination:** The reflector says "looks good" when the step clearly failed. Use concrete success criteria, not vibes.
- **Infinite re-planning:** Reflection keeps failing, re-planner keeps generating new plans. Set a max replanning budget (2-3 attempts).
- **Executor can't do the step:** The planner writes steps that require capabilities the executor doesn't have. Ground the planner in available tools.
- **State explosion:** Each cycle adds to state. Summarize completed steps rather than carrying full outputs.

## Framework fit

| Framework | Native support | Notes |
|-----------|----------------|-------|
| LangGraph | Planner, Executor, Reflector as graph nodes with conditional edges for re-planning | Best fit — state management handles plan evolution |
| Pydantic AI | Separate agents for planner/executor/reflector, manual orchestration | Works but you manage state yourself |
| Mastra | Workflow steps for plan/execute/reflect cycle | TS-native, workflow primitives help |
| CrewAI | Sequential crew with planner + executor agents | Possible but less control over reflection loop |
| Vercel AI SDK | Manual orchestration with `generateObject()` / `generateText()` | Lightweight but no built-in state management |

## Reference implementations

- [recipes/code-review-agent.md](../recipes/code-review-agent.md) — Plan-and-Execute code reviewer with LangGraph (skeleton)
