# Anti-Compositions

The [combination matrix](./combination-matrix.md) names which patterns pair well, which are complex, and which are redundant. This doc takes the *Complex* and *Redundant* cells and adds the *why-not*. If the matrix tells you which pairs to think twice about, this doc tells you why and what to do instead.

Most over-engineered agent systems aren't broken at any individual pattern — they're broken at the seams between patterns. Anti-compositions are the seams that look reasonable in design review and fall apart in production.

## Why anti-compositions matter

A pattern's failure modes are documented in its design doc. A composition's failure modes often aren't documented anywhere — they emerge from the interaction. Three classes of failure dominate:

- **Cost amplification.** Each pattern's per-call cost compounds with the next. Two patterns each "only" doubling cost produce a 4× system without anyone noticing in design review.
- **Hidden latency.** Sequential patterns stacked under a synchronous API turn second-scale interactions into minute-scale ones. The user-perceived shape of the system changes.
- **Overlap and ambiguity.** Two patterns doing similar work create contradiction zones. When they disagree, neither pattern's design tells you how to resolve it.

Below: the specific anti-compositions worth naming. None are *always* wrong. They're wrong as defaults — adopt them only when the simpler alternative has been measured and found insufficient.

## Patterns that fight each other

### Multi-Agent + Reflection on small tasks

**Symptom:** Adding reflection to a multi-agent system because *"quality matters"* — the supervisor delegates to workers, the workers each reflect on their output, the supervisor synthesizes.

**Why it's wrong as a default:** Multi-agent already carries 3–5× the cost and latency of a single agent. Reflection at least doubles per-worker cost and serializes by construction. On tasks the simpler patterns handle, you've spent 6–10× the budget for marginal quality gain that doesn't survive eval.

**When it's right:** High-stakes outputs where measured eval data shows the cost premium translates to value. Don't add reflection to multi-agent without an eval baseline.

**What to use instead:** Pick one. Reflection on a single ReAct agent often gets 80% of the quality gain at a fraction of the cost.

### RAG + ReAct without retrieval grounding

**Symptom:** A ReAct agent has a `retrieve_docs` tool but doesn't enforce citation in the final answer. The agent retrieves, reads, then writes whatever it wants.

**Why it's wrong:** RAG's value is *grounding*. Without enforcement, the agent treats retrieval as suggestion. You pay retrieval cost without getting the hallucination defense. Worse, the agent may cite retrieved chunks selectively — using one chunk to support a claim that the chunk doesn't actually support.

**When it's right:** Never, in this exact shape. The defect is the missing enforcement.

**What to use instead:** Either schema-enforce citations (claims must cite a retrieved span) or drop RAG and use the agent's parametric knowledge — at least you're not paying for retrieval you don't use.

### Memory + Multi-Agent without scoped writes

**Symptom:** Multiple worker agents read and write to the same shared memory store. Worker A writes a preference; Worker B sees and acts on it; Worker A's preference was wrong; the error propagates silently across the system.

**Why it's wrong:** Memory's failure mode is poisoning. Multi-agent's failure mode is propagation. Composed without per-agent scopes, every worker can poison every other worker. Debugging requires reconstructing a multi-actor write history — usually impossible after the fact.

**When it's right:** Read-mostly memory (one writer, many readers), or per-agent memory scopes that prevent cross-agent writes.

**What to use instead:** Either give each agent its own memory scope and surface cross-scope reads explicitly, or designate one *memory-writer* agent that owns all writes and accepts proposed writes from others through an approval surface.

### Plan & Execute + Reflection on the plan (without execution feedback)

**Symptom:** Reflect on the plan *before* executing any step. The critic critiques the plan, the planner revises, eventually you execute.

**Why it's nuanced:** This is actually a good idea — see the [Plan & Execute → Reflection composition pointer](../patterns/plan_and_execute/design.md). It fails when the critic has no execution feedback. A plan that *looks* good often fails at step 3 in ways the critic couldn't predict.

**When it's right:** Reflection on the plan + reflection on the executed result. Two reflection passes catch different failure modes.

**What to use instead:** Either skip pre-execution reflection and reflect on results, or add a post-execution reflection cycle for tasks where the plan-quality lift matters.

### Reflection on Routing decisions

**Symptom:** A reflection wrapper around the routing classifier — "first classify; now critique the classification; now classify again." The pipeline emits a route, the critic finds reasons to second-guess it, the router re-runs and picks a different route. The label distribution drifts over time even on identical traffic.

**Why it's wrong as a default:** Routing's value depends on label *stability*: the same input class should consistently land on the same route so downstream handlers, evals, and cost models can rely on the partition. Reflection's value depends on *change*: the critic always finds something to revise (see [Anti-Pattern #3 — Reflection without measurable criteria](../foundations/anti-patterns.md#3-reflection-without-measurable-criteria)). The two goals fight. After a few passes, the critic has talked the router into using the rarer labels because they look more "considered," and the routing precision metrics quietly degrade. The combination scores `complex` in the [combination matrix](./combination-matrix.md) for exactly this reason.

**When it's right:** When the route is genuinely ambiguous and the critic checks a *binary* gate (e.g., "is the confidence above 0.7 — yes / no?"). That isn't iterative reflection; it's an abstention rule. Implement it as a confidence threshold or an [`unknown`/`escalate` fallback](../patterns/routing/design.md), not a reflection loop.

**What to use instead:** Two cleaner options. (a) Tighten the route descriptions so the original classifier produces stable picks (per [Anti-Pattern #9 — Overlapping route descriptions](../foundations/anti-patterns.md#9-overlapping-route-descriptions-in-routing)). (b) Add reflection *inside the chosen handler*, after routing has committed — the reflection improves the handler's output without destabilizing the partition.

### Evaluator-Optimizer + Reflection

**Symptom:** Generate output → reflect → revise → evaluate → optimize → reflect → revise → evaluate...

**Why it's wrong:** Evaluator-Optimizer *is* a reflection loop, just with an external scoring signal instead of a self-critique. Stacking them stacks two convergence mechanisms with different criteria. They oscillate against each other — the reflector wants stylistic improvement, the evaluator wants the metric to climb, neither wins.

**When it's right:** Almost never. The two patterns solve the same problem.

**What to use instead:** Pick one. Evaluator-Optimizer when you have a measurable target; Reflection when criteria are softer or the evaluator itself is hard to build.

## Patterns that overlap

### Routing + Multi-Agent supervisor

**Symptom:** A routing layer classifies the request into one of N intents, then hands off to a multi-agent system whose supervisor's first action is to classify the request and pick a worker.

**Why it's redundant:** Two classifiers in series. The router's output is the supervisor's input; the supervisor re-derives the same classification. Cost paid twice; failure surface doubled.

**When it's right:** When the router and the supervisor classify on *different dimensions* (router picks a deployment cluster; supervisor picks which worker within the cluster). Document the difference explicitly.

**What to use instead:** Collapse to one classifier. Either the router calls workers directly, or the supervisor handles routing as its first internal step.

### Orchestrator-Worker + Plan & Execute

**Symptom:** A planner generates a plan, then for each step delegates to a worker. An orchestrator decomposes the task, then delegates to workers.

**Why it's redundant:** Both patterns *are* "decompose then dispatch." Orchestrator-Worker is dynamic (decomposition is one LLM call inside an outer LLM call). Plan & Execute is static (plan generated upfront, then executed). Composing them means decomposing twice.

**When it's right:** Plans contain orchestrator-worker steps as *sub-shapes* — fine. A plan that says "decompose this step into sub-steps" is just Plan & Execute with a recursive step.

**What to use instead:** Pick the decomposition timing. Plan & Execute when the decomposition is stable enough to commit upfront. Orchestrator-Worker when decomposition emerges during execution.

### Memory + RAG over the same corpus

**Symptom:** Both the memory subsystem and the RAG subsystem index the same documents — chat history, knowledge base — into the same vector store with the same chunking.

**Why it's redundant:** Memory is *time-ordered, agent-owned* context. RAG is *topic-organized, externally-authored* knowledge. Indexing them identically loses the type distinction, and both subsystems' retrieval logic ends up duplicated.

**When it's right:** Same vector store *infrastructure*, different namespaces — fine, even encouraged. Same namespace is the anti-composition.

**What to use instead:** Separate namespaces with separate retrieval logic. Memory retrieval is recency-weighted; RAG retrieval is similarity-weighted. The two queries should land in different result sets.

## Patterns whose composition leaks state

### Multi-Agent + Long-Term Memory without provenance tags

**Symptom:** Workers write to shared long-term memory; the supervisor (or future workers) read memories without knowing which worker wrote them.

**Why it's broken:** A poisoned worker poisons the long-term memory; *all future agents* inherit the poison. There's no provenance, so there's no way to roll back selectively or down-weight a low-trust source.

**Defense:** Memory entries carry `source: worker_X` tags. Trust scoring per source. Audit log of writes.

### Saga + Agent-Driven Steps without compensation contracts

**Symptom:** A saga step delegates to an agent. The agent decides what to do. The compensator assumes a specific side effect was issued — but agents are non-deterministic, and the compensator's assumption is wrong some of the time.

**Why it's broken:** Saga's compensator contract requires `do` to issue a known side effect that `undo` can reverse. An agent's output is variable. The compensator that worked in testing fails in the long tail.

**Defense:** Saga steps that wrap agents should constrain the agent's output to a fixed schema. The compensator reverses *that schema*, not whatever the agent happens to have done.

### Event-Driven + ReAct without per-event isolation

**Symptom:** An event-driven system invokes a ReAct agent per event. The ReAct agent uses shared in-process state (cache, memory, tool registry).

**Why it's broken:** Events arrive concurrently. Two ReAct loops sharing state can race — one updates the tool registry while another is mid-iteration; one reads stale memory; one's tool result is consumed by the wrong loop.

**Defense:** Per-event isolation. Each event's ReAct loop runs with its own state instance. Shared infrastructure (vector store, LLM client) is fine; shared *mutable* state is not.

## What to use instead — quick reference

| If you were going to use… | Consider first |
|---|---|
| Multi-Agent + Reflection on small tasks | Single agent + Reflection |
| RAG + ReAct without citation enforcement | Either: enforce citation; or drop RAG |
| Memory + Multi-Agent without scopes | Per-agent memory scopes + audit log |
| Plan + Reflection without execution feedback | Plan + Reflection + post-execution Reflection |
| Reflection on Routing decisions | Tighten route descriptions; reflect inside the chosen handler |
| Evaluator-Optimizer + Reflection | Pick one |
| Routing + Multi-Agent supervisor (same classification) | One classifier |
| Orchestrator-Worker + Plan & Execute | Decide decomposition timing; pick one |
| Memory + RAG over the same namespace | Separate namespaces |

## How to find these in your own architecture

When two patterns are composed, ask:

1. **Do they overlap in intent?** If both patterns answer "what should I do next?", they overlap.
2. **Do they share state?** If both read or write the same store, they share state. Make ownership explicit.
3. **Do they amplify cost?** Multiply per-pattern cost. If the result is your monthly LLM bill, reconsider.
4. **Do they amplify latency?** Sequential composition adds; concurrent composition usually doesn't.
5. **Are their failure modes independent?** If pattern A's failure cascades through pattern B, the composition has a single point of failure that neither pattern's docs describe.

If two patterns answer the same question, share the same state, or amplify the same cost/latency curve, treat the composition as suspect until measured.

## Related

- [Combination Matrix](./combination-matrix.md) — the analytical table this doc gives prose to.
- [Reference Architectures](./reference-architectures.md) — composed systems that *do* work; useful contrast.
- [Anti-Patterns](../foundations/anti-patterns.md) — single-pattern anti-patterns; this doc extends to multi-pattern ones.
- [Choosing a Pattern](../foundations/choosing-a-pattern.md) — pick the simplest pattern first; composition is the upgrade path, not the default.
