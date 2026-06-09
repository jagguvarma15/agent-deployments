# Cost & Model Selection

Pattern selection determines *what shape of cost* you commit to. Model selection determines *how much* that shape costs per call. This doc covers both — the model-tier decision (Haiku / Sonnet / Opus / external), the per-pattern cost shape, and the guardrails that keep the bill bounded.

Per-pattern cost specifics still live in each pattern's `cost-and-latency.md`. This is the cross-cutting frame those documents specialize.

## Model tier selection

Most agent stacks have access to three tiers from one provider plus selected external models. The right model for a step is rarely the most capable one available — it's the smallest one that does the job reliably enough.

### Decision tree

- **Classification, routing, structured extraction, tool selection from a short list, refusal detection** → fastest, cheapest tier (Haiku-class). These are constrained tasks where the model picks among a small enumeration; large models add latency, not accuracy.
- **General-purpose generation, summarization, multi-step reasoning, code generation for common tasks** → mid tier (Sonnet-class). Default for most agent loops, including the loop itself in ReAct and Plan & Execute.
- **Long-horizon planning, deep multi-step reasoning, code generation for novel problems, eval grading where you need the grader to outperform the generator** → highest tier (Opus-class). Reach for this when the failure mode of the mid tier is "the answer is plausible but wrong in subtle ways."
- **Specialized tasks** → external models. Embedding generation, classification for safety / content moderation, OCR, speech, vision-only tasks. Use the right tool, not the universal one.

### Mixed-tier within one agent

A well-designed agent uses multiple tiers. Examples:

- **ReAct loop:** Sonnet for reasoning, Haiku for tool-output formatting, Opus for the final summary.
- **Multi-agent system:** Sonnet workers, Opus supervisor, Haiku router.
- **Eval pipeline:** Sonnet generator + Opus grader (the grader must outclass the generator to be useful).

Don't homogenize unless the cost difference is negligible. Per-call differences compound over loops.

### When to reach for an external model

- The task is OOD for the foundation models (specialized domain, non-English, structured-data-specific).
- The economics flip — small specialized models can be 10× cheaper for the right task.
- The data can't leave your perimeter, and you have the infra to host.

External models add operational overhead (deployment, fine-tuning pipelines, drift management). Justify the switch with a measured baseline, not a hunch.

## Token budgets

A token budget is a structural cap, not a soft suggestion. Three layers:

- **Per-call budget.** Each LLM call has a max-tokens cap on input and output. Models have hard limits; your budget should be tighter to fail fast on prompt explosions.
- **Per-session / per-request budget.** Sum of tokens across all calls in one user-facing transaction. Catches runaway loops.
- **Per-day budget.** Aggregate across the deployment, per cost center. Catches abuse and runaway batch jobs.

When a budget trips, options:

- Fail the request and return a meaningful error.
- Downgrade gracefully (truncate context, switch to a cheaper model, use a cached answer).
- Escalate to a human queue.

The right choice depends on the use case. The wrong choice is *no behavior* — uncapped cost is a denial-of-wallet vulnerability. See [Security & Safety](./security-and-safety.md).

## Per-pattern cost shape

Patterns have characteristic cost profiles. Use this table to estimate before you build.

| Pattern | Cost shape | Where cost concentrates |
|---|---|---|
| [Prompt Chaining](../workflows/prompt-chaining/overview.md) | Linear in steps | Total prompt size grows if each step accumulates context. |
| [Parallel Calls](../workflows/parallel-calls/overview.md) | N parallel + 1 aggregation | Fan-out width is the lever. |
| [Orchestrator-Worker](../workflows/orchestrator-worker/overview.md) | 1 plan + N workers + 1 synth | Plan and synth are expensive (full context); workers are cheaper. |
| [Evaluator-Optimizer](../workflows/evaluator-optimizer/overview.md) | 2× per iteration; multiple iterations | Cap iterations explicitly. |
| [ReAct](../patterns/react/overview.md) | Variable per step; unbounded without cap | Each step appends the prior observation; context grows. |
| [Plan & Execute](../patterns/plan_and_execute/overview.md) | 1 plan + N steps + 0–1 replan | Plan is expensive; per-step cost dominates over enough steps. |
| [Tool Use](../patterns/tool_use/overview.md) | 1 call per tool decision | Tool execution cost (paid APIs) often exceeds LLM cost. |
| [Memory](../patterns/memory/overview.md) | Linear in retrieved memories | Compression and summarization keep this bounded. |
| [RAG](../patterns/rag/overview.md) | Retrieval (cheap) + generation (medium) | Generation cost scales with retrieved context size. |
| [Reflection](../patterns/reflection/overview.md) | 2–N× per iteration | Iteration cap is the lever. |
| [Routing](../patterns/routing/overview.md) | 1 classifier call + downstream pattern cost | Classifier is cheap; downstream dominates. |
| [Multi-Agent](../patterns/multi_agent/overview.md) | Sum of agent-call costs + orchestration overhead | Supervisor + N workers; supervisor cost is per-handoff. |
| [Event-Driven](../patterns/event_driven/overview.md) | Per-event agent cost | Event rate × per-event cost; rate-limit per partition. |
| [Saga](../patterns/saga/overview.md) | Steps + potential compensations | Compensations amplify cost on failure. |
| [Human in the Loop](../patterns/human_in_the_loop/overview.md) | Low LLM cost; high human-time cost | Cost shape changes; budget human review time. |

## The latency / cost / quality triangle

Pick two. Most architectural decisions trade off one of these against the others:

- **Faster + cheaper** → fewer steps, smaller model, no iteration (Prompt Chaining, Tool Use with Haiku).
- **Faster + higher-quality** → larger model, no iteration, parallel calls (Parallel Calls with Opus).
- **Higher-quality + cheaper** → smaller model with iteration (Evaluator-Optimizer with Sonnet, Reflection with Sonnet).

There's no path to *fast + cheap + high-quality* — claims to the contrary are almost always undisclosed tradeoffs (lower quality bar, cached answers, narrow domain).

When stakeholders push for all three: name the tradeoff explicitly and pick the right two.

## Cost guardrails

Guardrails make cost predictable. The set that consistently works:

- **Iteration caps** on every loop pattern. `max_steps` is the single most important agent parameter.
- **Token caps** per call and per session.
- **Tool-call caps** per agent instance per minute. Catches infinite-tool-loop bugs.
- **Daily aggregate caps** with alerting at 50% / 80% / 100% of budget.
- **Per-tenant / per-user budgets** for multi-tenant systems.
- **Per-environment budgets.** Dev / staging should have hard caps below production — dev mistakes shouldn't bankrupt the team.

Alerting is not a cap. A cap stops cost; an alert tells you that cost is happening. You need both.

## What's deferred to `agent-deployments`

The operational cost layer — provider-level rate limits, autoscaling policy, autoscaling triggers, cost dashboards, alerting integration — lives in [`agent-deployments/docs/cross-cutting/observability.md`](https://github.com/jagguvarma15/agent-deployments/blob/main/docs/cross-cutting/observability.md) and [`docs/capabilities/obs/`](https://github.com/jagguvarma15/agent-deployments/tree/main/docs/capabilities/obs). This doc covers what to think about at the architecture layer; the deployment layer covers what to instrument.

## Related

- Per-pattern `cost-and-latency.md` files in each `patterns/*/` and `workflows/*/` directory specialize this with pattern-specific token counts and latency estimates.
- [Security & Safety → Denial of wallet](./security-and-safety.md) — cost guardrails are also a security control.
- [Evals & Quality → Eval cost budgets](./evals-and-quality.md) — eval pipelines have their own cost shape.
- [Choosing a Pattern](./choosing-a-pattern.md) — pattern selection is the first cost lever.

## What this guide deliberately doesn't cover

- Specific dollar figures per model. Provider pricing changes; the patterns don't.
- Provider-specific batch / cache / commitment pricing. Read the provider's docs.
- Cost modeling spreadsheets — those are organizational artifacts, not architectural ones.
- "Which provider is cheapest" — depends on workload shape and changes too fast to enshrine in docs.
