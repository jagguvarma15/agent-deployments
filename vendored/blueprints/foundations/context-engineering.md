# Context Engineering

Memory is one slice of a bigger discipline. **Context engineering** is the architectural framing that decides *what enters the model's context window, in what shape, and on whose authority* — across every turn of every loop. Picking the right pattern (Choosing a Pattern), the right model (Cost & Model Selection), and the right memory store (the [Memory](../primitives/memory/overview.md) primitive) all bottom out here: every architectural decision moves tokens into or out of context.

This doc covers the cross-cutting frame. Per-pattern context specifics still live in each pattern's `design.md` (under "Context Engineering" or "State"). This is the vocabulary those documents specialize.

## Context is a finite resource

The context window is not a bucket you fill; it's an attention budget you spend. As token counts grow, recall degrades — the field calls this **context rot**: with enough irrelevant tokens, even the right token gets lost. Long-context benchmarks (needle-in-a-haystack, LOCA-bench) show measurable accuracy drops well before the published limit. Practical takeaways:

- Treat the window as a budget with diminishing returns, not a hard limit you fill until it errors.
- Measure tokens used per call and per loop iteration; rising tokens with flat task progress is a leading indicator of a broken loop.
- Optimize for the *smallest sufficient context* that lets the model take the next correct step — not the largest context the window allows.

## The four levers

Every context decision is one of four moves. Most production failures come from skipping one.

- **Select** — decide what goes in. Prompt structure, retrieved chunks, tool descriptions, conversation history, memory recalls.
- **Compress** — make what's in smaller. Summarization, structured extraction, schema-bound recap of prior turns.
- **Prune** — take things out. Drop stale tool results, drop completed plan steps, drop earlier reasoning when only the conclusion matters next.
- **Persist** — push things outside the window for later recall. File-based memory, vector stores, scratch-pads, a virtual filesystem the agent reads and writes.

Skilled context engineering is sequencing these four across the loop. ReAct that never prunes will rot mid-trajectory; Plan & Execute that never persists will forget what step 2 produced by step 7.

## Memory hierarchy

Classical OS memory hierarchies (registers → cache → RAM → disk) map cleanly onto agents:

| Tier | Where it lives | Latency | Use for |
|---|---|---|---|
| **Working context** | The current LLM call | Free (already loaded) | The active goal, the in-flight tool call, the next decision |
| **Session state** | An in-memory state object or checkpoint | Per-call serialize | Conversation turns, partial plan, recent tool results |
| **Short-term store** | Local file, scratchpad, agent-owned KV | One read per recall | Mid-task notes, intermediate artifacts |
| **Long-term store** | DB or vector store outside the agent process | Network round-trip | Cross-session facts, learned preferences, retrieved knowledge |
| **External world** | Tools, retrieval, MCP servers | Variable | Authoritative state the agent doesn't own |

The [Memory](../primitives/memory/overview.md) primitive covers the bottom two tiers. Context engineering owns the *movement* between tiers: when to promote a working-context fact to long-term, when to evict, when to recall.

## Per-pattern context shape

Patterns differ in how context grows. Use this to estimate before you build.

| Pattern | Context shape | Where it concentrates |
|---|---|---|
| [Prompt Chaining](../patterns/prompt-chaining/overview.md) | Grows linearly if each step accumulates prior output | Compress between steps; don't pass the full prior call forward |
| [Parallel Calls](../patterns/parallel-calls/overview.md) | Bounded per call; aggregator gets the union | The aggregation step is the budget risk |
| [Orchestrator-Worker](../patterns/orchestrator-worker/overview.md) | Workers get scoped sub-context; synth gets all worker outputs | Synthesizer is the risk; pass summaries, not transcripts |
| [ReAct](../patterns/react/overview.md) | Unbounded without intervention — every observation appends | Iteration cap + per-step compaction; prune completed sub-goals |
| [Plan & Execute](../patterns/plan_and_execute/overview.md) | Plan once (large), per-step (small) | Persist completed-step outputs to a scratchpad; don't reload them |
| [Multi-Agent](../patterns/multi_agent/overview.md) | Each sub-agent has its own window; supervisor sees handoffs | Supervisor context is the risk surface; sub-agent windows are isolated |
| [RAG](../patterns/rag/overview.md) | Retrieval-size × chunk-size per call | Re-rank to small-k; chunk size is a quality/cost lever |
| [Reflection](../patterns/reflection/overview.md) | 2× per iteration plus critique transcript | Cap iterations; persist only the final critique, not the full chain |
| [Saga](../patterns/saga/overview.md) | Step-local; saga log lives outside the window | Compensation context comes from the log, not the LLM's memory |
| [Event-Driven](../patterns/event_driven/overview.md) | One window per event by default | Cross-event state must be persisted; the LLM is stateless across events |

## Context-window awareness

The 2026 inflection: agents that *know* their remaining budget make different decisions than agents that don't. Two patterns to keep in scope:

- **Context-capacity feedback after each tool call.** The agent sees "X tokens remaining of Y" alongside the tool result. The agent can decide to summarize, persist, or escalate. This is a structural decision, not a prompt-engineering one — it requires the loop to surface budget as state.
- **Programmatic context management.** The model executes small code blocks to load, summarize, or move context, rather than asking the orchestrator to do it. Useful when the loop and the model need to negotiate budget mid-task.

These are not patterns themselves; they are *capabilities* a pattern can opt into. Most patterns benefit from the first; the second is overkill for simple workflows.

## Compaction and tool clearing

Two specific moves under the **compress** + **prune** levers:

- **Compaction** — periodically replace the running context with a structured recap. Common cadence: at iteration boundaries, after long tool outputs, before a plan revision. Compaction is a model call itself; budget for it.
- **Tool clearing** — when a tool returns hundreds of lines (search results, file listings, error logs), the loop should clear the raw response after extracting what's needed. Otherwise the next iteration carries the noise.

Both moves are lossy. The art is choosing what to lose. Keep: the goal, the active sub-plan, decisions made, distinct facts. Drop: raw tool input/output verbatim, reasoning steps that led to decisions already taken, exploratory branches the agent rejected.

## Budgets and guardrails

Mirror the cost guardrails in [Cost & Model Selection](./cost-and-model-selection.md), but for tokens-in:

- **Per-call input cap.** Hard cap below the model's limit so prompt explosion fails fast.
- **Per-loop budget.** Sum of input tokens across all iterations of one user request. Catches runaway loops earlier than wall-clock.
- **Compaction trigger.** When session tokens exceed X% of the per-loop budget, force a compaction step.
- **Persist trigger.** When working context approaches the per-call cap, promote oldest distinct facts to long-term store before truncating.

Alerting on these is not a substitute for capping them. Uncapped context is the upstream cause of both runaway cost and context rot.

## What's the same as cost? What's different?

Context engineering and cost engineering share most of the same levers (caps, compaction, summarization, persistence), but they optimize for different things:

| Lever | Cost goal | Context goal |
|---|---|---|
| Compaction | Fewer tokens billed | Sharper recall on the active goal |
| Pruning | Fewer tokens billed | Less attention distraction |
| Persistence (external store) | Cheaper than token rent | Survives the window's eviction |
| Smaller model | Lower $/call | Often *smaller* context window — context engineering gets harder |

When the two goals conflict (e.g., a longer system prompt would improve recall but costs more per call), context engineering wins the architecture decision and cost engineering wins the configuration decision. Don't mix them up.

## Cross-cutting concerns

- **Security.** Untrusted text in context is the prompt-injection surface. Compress and prune *before* the privileged decision step, not after, and confine untrusted text to a quarantined LLM where possible. See [Security & Safety](./security-and-safety.md) and the [Guardrails](../modifiers/guardrails/overview.md) modifier.
- **Hallucination.** Insufficient context is the leading cause of grounded answers being wrong. Selecting the right tokens beats adding more tokens. See [Hallucination & Grounding](./hallucination-and-grounding.md).
- **Evals.** Trace evals should record token counts per call and per loop, not just task completion. Without that signal, context rot looks like model regression. See [Evals & Quality](./evals-and-quality.md).

## What's deferred to `agent-deployments`

The operational layer — context-window telemetry, alerting, dashboards for token-per-request percentiles, autoscaling on context pressure — lives in the deployment repo. This doc covers what to think about at the architecture layer; the deployment layer covers what to instrument.

## Related

- [Memory](../primitives/memory/overview.md) — the storage primitive that backs the long-term tier
- [Cost & Model Selection](./cost-and-model-selection.md) — the cost framing that shares most of the same levers
- [Choosing a Pattern](./choosing-a-pattern.md) — pattern selection is the first context-shape lever
- [Evals & Quality](./evals-and-quality.md) — measuring whether your context engineering is working

## What this guide deliberately doesn't cover

- Specific token counts per model. Provider limits change; the architecture doesn't.
- Provider-specific cache / prefix-reuse pricing. Read the provider's docs.
- Embedding model selection for retrieval. That's a [RAG](../patterns/rag/overview.md) decision.
- Prompt templates. Those are pattern-specific and live in each pattern's `prompts/`.
