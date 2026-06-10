# Choosing a Pattern

Designing an agent is **three orthogonal decisions**, not one. Use this guide in that order:

```
1. Pick a PATTERN     (one)       — what flow shape your agent follows
2. Pick PRIMITIVES    (zero or more) — what building blocks the agent uses
3. Pick MODIFIERS     (zero or more) — what transformations apply
```

The pattern decides the agent's *shape* (loop, plan, retrieve, classify, …). Primitives are orthogonal building blocks the agent uses inside that shape — they don't change the shape; they're things the shape consults. Modifiers wrap a chosen pattern with a transformation (a human-approval gate, an audit overlay) without changing the underlying flow.

Most of this document focuses on step 1 (pattern picking) because it's the foundational choice. Steps 2 and 3 are quick checklists at the bottom.

## Step 1 — Pick a pattern

Use the decision flowchart, then refine with the detailed guidance below.

## Decision Flowchart

```mermaid
graph TD
    Start([What does your system need to do?]) --> Q0{Is the trigger an<br/>external event<br/>not a user request?}

    Q0 -->|"Yes — queue/stream event"| EventDriven([Event-Driven])
    Q0 -->|"No — user request"| QHITL{Action is high-stakes<br/>and must require<br/>human approval?}
    QHITL -->|"Yes"| HITL([Human in the Loop])
    QHITL -->|"No"| QSaga{Multi-step process where<br/>intermediate steps must be<br/>undone on failure?}
    QSaga -->|"Yes"| Saga([Saga])
    QSaga -->|"No"| Q1{Does the LLM need to<br/>take actions or use tools?}

    Q1 -->|"No — text in, text out"| Q2{Multiple processing steps?}
    Q2 -->|"No"| Single([Single LLM Call<br/>No pattern needed])
    Q2 -->|"Yes"| Q3{Steps independent<br/>of each other?}
    Q3 -->|"Yes"| Parallel([Parallel Calls])
    Q3 -->|"No — sequential"| Q4{Need quality iteration?}
    Q4 -->|"No"| Chain([Prompt Chaining])
    Q4 -->|"Yes"| EvalOpt([Evaluator-Optimizer])

    Q1 -->|"Yes — needs tools"| Q5{Can you define the<br/>exact steps in advance?}
    Q5 -->|"Yes"| Q6{Multiple specialized<br/>workers needed?}
    Q6 -->|"No"| ToolUse([Tool Use])
    Q6 -->|"Yes"| OrcWorker([Orchestrator-Worker])

    Q5 -->|"No — LLM must decide"| Q7{Need to break task<br/>into a plan first?}
    Q7 -->|"No — step by step"| Q8{Need external<br/>knowledge?}
    Q8 -->|"No"| ReAct([ReAct])
    Q8 -->|"Yes"| RAG([RAG + ReAct])

    Q7 -->|"Yes"| Q9{Single agent<br/>sufficient?}
    Q9 -->|"Yes"| PlanExec(["Plan & Execute"])
    Q9 -->|"No"| MultiAgent([Multi-Agent])

    style Start fill:#e3f2fd
    style Single fill:#e8f5e9
    style Chain fill:#c8e6c9
    style Parallel fill:#c8e6c9
    style EvalOpt fill:#c8e6c9
    style OrcWorker fill:#c8e6c9
    style ToolUse fill:#a5d6a7
    style ReAct fill:#81c784
    style RAG fill:#81c784
    style PlanExec fill:#66bb6a
    style MultiAgent fill:#4caf50
    style EventDriven fill:#4caf50
    style Saga fill:#4caf50
    style HITL fill:#66bb6a
```

Green intensity indicates increasing complexity. Start as light as possible.

## Quick Reference Table

> For a framework-specific view of these patterns (LangGraph, Claude Agent SDK, CrewAI, AutoGen, LlamaIndex, MCP), see [Frameworks & Integrations](./frameworks-and-integrations.md).
>
> Each pattern's overview has a fuller "When NOT to use this pattern" section. This table is the at-a-glance view.

| Pattern | Type | Use When | Don't Use When |
|---------|------|----------|----------------|
| [Prompt Chaining](../patterns/prompt-chaining/overview.md) | Workflow | Fixed multi-step text processing | Steps depend on dynamic decisions |
| [Parallel Calls](../patterns/parallel-calls/overview.md) | Workflow | Independent tasks that can run concurrently | Tasks depend on each other's output |
| [Orchestrator-Worker](../patterns/orchestrator-worker/overview.md) | Workflow | Complex task needs decomposition into subtasks | Task is simple enough for one call |
| [Evaluator-Optimizer](../patterns/evaluator-optimizer/overview.md) | Workflow | Output quality needs iterative refinement | First-pass quality is sufficient |
| [ReAct](../patterns/react/overview.md) | Agent | Open-ended tasks with tool use | Steps are predictable in advance |
| [Plan & Execute](../patterns/plan_and_execute/overview.md) | Agent | Complex tasks needing upfront strategy | Simple tasks with fewer than 3 steps |
| [Tool Use](../primitives/tool_use/overview.md) | Primitive | LLM needs to interact with external systems | No external actions needed |
| [Memory](../primitives/memory/overview.md) | Primitive | Context must persist across conversations | Single-turn interactions |
| [RAG](../patterns/rag/overview.md) | Agent | LLM needs external knowledge to answer | All needed knowledge fits in context |
| [Reflection](../patterns/reflection/overview.md) | Agent | Output quality must exceed single-pass | Latency is more important than quality |
| [Routing](../patterns/routing/overview.md) | Agent | Different inputs need different handling paths | All inputs follow the same process |
| [Multi-Agent](../patterns/multi_agent/overview.md) | Agent | Task requires multiple specialized capabilities | Single agent can handle the scope |
| [Event-Driven](../patterns/event_driven/overview.md) | Agent | Trigger is an external event (cancellation, status change, scheduled job) | User is waiting synchronously for a response |
| [Saga](../patterns/saga/overview.md) | Agent | Long-running multi-step process with steps that have to be undone on failure | All steps live in one DB that supports transactions |
| [Human in the Loop](../modifiers/human_in_the_loop/overview.md) | Agent | High-stakes action must not commit without human approval | Action is low-stakes and review would be a rubber-stamp |

## Decision Criteria

### 1. Predictability vs Flexibility

**If you can enumerate the steps your system will take**, use a workflow. Workflows are deterministic (given the same input, they follow the same path), easy to test, and cheap to debug.

**If the steps depend on what the LLM discovers at runtime**, use an agent. Agents handle novel situations but are harder to predict and test.

**Rule of thumb:** Start with a workflow. Promote to an agent only when the conditional logic in your workflow code becomes unmanageable.

### 2. Latency Budget

Every LLM call adds latency. Patterns with loops (ReAct, Reflection, Evaluator-Optimizer) multiply this by the number of iterations.

| Pattern | Typical LLM Calls | Latency Profile |
|---------|-------------------|-----------------|
| Prompt Chaining | N (number of steps) | Linear, predictable |
| Parallel Calls | 1 round (parallel) + 1 (aggregate) | Low — parallel execution |
| Orchestrator-Worker | 1 (plan) + N (workers) + 1 (synthesize) | Medium, partially parallelizable |
| ReAct | 1–10+ (depends on task) | Variable, unpredictable |
| Plan & Execute | 1 (plan) + N (steps) + 0–1 (replan) | Medium-high |
| Multi-Agent | Varies widely | High, depends on delegation depth |

### 3. Cost Budget

Cost scales with tokens processed. Patterns that iterate (reflection, evaluation loops) or maintain long message histories (agents, memory) consume more tokens.

**Cost-sensitive?** Prefer workflows with short chains. Avoid open-ended agent loops without iteration caps.

### 4. Error Tolerance

Some systems can tolerate occasional LLM errors (a chatbot gives a mediocre answer). Others cannot (a code generation pipeline produces syntax errors).

**Low error tolerance?** Add evaluation loops (Evaluator-Optimizer or Reflection) or compose with validation tools.

### 5. Task Complexity

Match pattern complexity to task complexity:

```mermaid
graph LR
    Simple["Simple Task<br/>(classify, extract, summarize)"] --> WF["Use a Workflow<br/>or single LLM call"]
    Medium["Medium Task<br/>(research, analyze, generate + validate)"] --> Agent["Use ReAct or<br/>Plan & Execute"]
    Complex["Complex Task<br/>(multi-domain, multi-step, collaborative)"] --> MA["Use Multi-Agent<br/>or composed patterns"]

    style Simple fill:#e8f5e9
    style WF fill:#e8f5e9
    style Medium fill:#fff3e0
    style Agent fill:#fff3e0
    style Complex fill:#fce4ec
    style MA fill:#fce4ec
```

## Common Combinations

Patterns are composable. Most production systems use more than one:

- **RAG + ReAct** — Agent that retrieves knowledge before reasoning. The most common production pattern.
- **Plan & Execute + Tool Use** — Planner generates strategy, executor uses tools at each step.
- **Multi-Agent + Memory** — Agents that remember previous interactions and learn.
- **Routing + specialized workflows** — Classifier directs to purpose-built pipelines.
- **Reflection + any generator** — Adds self-critique loop to improve output quality.

See [Composition](../composition/README.md) for detailed combination guidance.

## Anti-Patterns

### Over-engineering
Using a multi-agent system when a prompt chain would work. **Cost:** Higher latency, more failure points, harder debugging. **Fix:** Start simple, add complexity only when you hit the limits of simpler patterns.

### Under-constraining Agents
Giving an agent access to many tools without iteration limits or scope restrictions. **Cost:** Runaway loops, high token usage, unpredictable behavior. **Fix:** Always set max iterations, restrict tool sets, validate outputs.

### Skipping Workflows
Jumping straight to agent patterns without considering whether a workflow would suffice. **Cost:** Unnecessary complexity and cost. **Fix:** Use the decision flowchart above — if you can enumerate the steps, use a workflow.

### Ignoring Composition
Building one monolithic pattern instead of composing simpler ones. **Cost:** Rigid, hard to modify, hard to test. **Fix:** Design with composition in mind from the start.

---

## Step 2 — Pick primitives (zero or more)

Primitives are the building blocks the agent uses inside whatever pattern you picked. They're orthogonal to the pattern — same questions, same answers, regardless of which flow shape you're in.

<!-- AUTO:choose-primitive-table -->
| Question | Add this |
|---|---|
| Does the agent need state that persists across sessions or conversations? | [`memory`](../primitives/memory/overview.md) |
| Does the agent need codified procedural knowledge (your org's review checklist, citation format, lookup-and-summarize routine)? | [`skills`](../primitives/skills/overview.md) |
| Is Sub-agents the right shape for your use case? | [`sub_agents`](../primitives/sub_agents/overview.md) |
| Does the agent need to invoke functions / call APIs / interact with structured systems? | [`tool_use`](../primitives/tool_use/overview.md) |
<!-- /AUTO -->

A typical agent declares 1-3 primitives. Tool use is the default; memory and skills layer on as needed.

## Step 3 — Pick modifiers (zero or more)

Modifiers wrap your chosen pattern with a transformation. They don't change the flow's core shape; they overlay a concern.

<!-- AUTO:choose-modifier-table -->
| Question | Add this |
|---|---|
| Is Guardrails the right shape for your use case? | [`guardrails`](../modifiers/guardrails/overview.md) |
| Does the agent take high-stakes actions that should require human approval before commit? | [`human_in_the_loop`](../modifiers/human_in_the_loop/overview.md) |
<!-- /AUTO -->

Most production agents add zero modifiers — that's fine. HITL is the canonical example for now; future modifiers (audit overlays, dual-LLM filters, etc.) will plug in here.

## End-to-end example

A research agent that answers questions by iteratively searching, citing, and persisting context:

```yaml
pattern:    react             # think → act → observe loop
primitives: [tool_use, memory] # has tools; remembers across turns
modifiers:  []                 # no human approval needed
```

A code review agent that runs LLM-emitted shell commands and asks a human to approve high-impact PRs:

```yaml
pattern:    plan_and_execute       # plan first, then execute
primitives: [tool_use, skills]     # has tools; has review-checklist skills
modifiers:  [human_in_the_loop]    # approval gate before destructive commits
```
