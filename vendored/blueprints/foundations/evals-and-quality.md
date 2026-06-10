# Evals & Quality

Evals are tests for systems where correctness is statistical, not Boolean. This doc covers how to design eval suites, how to pick metrics, and how to run evals in CI rather than as occasional reports.

It builds on, and does not duplicate, [Testing Strategies](./testing-strategies.md), which covers the test pyramid (unit, component, integration, eval) and what each layer mocks. The split:

- *Testing Strategies* — where evals fit in the pyramid and how the other layers complement them.
- *This doc* — how the eval layer specifically is built, run, and maintained.

## Evals are tests, not benchmarks

A benchmark is a one-time measurement against an external dataset. An eval suite is a continuously-run test suite the team owns, drawn from real use cases, that fails the build when output quality drops.

The mindset shift:

- **Benchmarks compare models.** Evals compare *your system* across changes.
- **Benchmarks publish a number.** Evals gate deployments.
- **Benchmarks are static.** Evals grow with every observed production failure.

If your "evals" only run before a model swap, they're benchmarks. Move them into CI.

## Designing a golden dataset

A golden dataset is the input side of the eval suite — inputs paired with expected behavior. Three properties matter more than size:

- **Coverage of real distributions.** Sampled from production traffic (with privacy review) rather than synthetic. Include the long tail, not just the headline use cases.
- **Coverage of failure modes.** Every production incident becomes a row. The golden dataset is also the regression suite.
- **Ground-truth honesty.** Where ground truth is ambiguous (open-ended generation), record the *acceptance criteria*, not a single expected string. Model-graded evals score against criteria, not exact match.

Concrete inclusions:

- Happy-path inputs covering each major intent.
- Adversarial inputs (prompt-injection attempts, ambiguous inputs, refusal cases).
- Inputs that should produce abstention / "I don't know" outputs.
- Inputs that should escalate to human review (HITL patterns).
- Edge-case inputs from incidents.

### Keeping it from getting stale

- **Append every production failure.** When you fix a bug, the input goes into the golden dataset before you close the ticket.
- **Sample monthly.** Replace the oldest 10% with fresh production samples to track distribution drift.
- **Decay obsolete cases.** If a case has been passing for a year and the underlying feature is stable, demote it to a smoke test.

### Handling ambiguous ground truth

- **Acceptance criteria over exact match.** *"The answer mentions {fact A, fact B} and does not claim X"* beats *"The answer equals: …"*
- **Multiple acceptable answers.** Record several valid outputs; pass if the system matches any.
- **Confidence ranges.** *"Confidence between 0.7 and 0.95"* is a better assertion than *"Confidence equals 0.85"*.
- **When in doubt, model-graded.** A second LLM call scores against the criteria. See below.

## Metric selection

Three families of metrics, used together:

### Rule-based metrics

Deterministic checks: schema validity, JSON parsability, presence of required fields, citation presence, tool-call legitimacy (function in allow-list, args match schema), refusal detected on refuse-list cases.

- **Cheap and fast.** Run on every input in the suite.
- **No false positives** — if the schema is wrong, the schema is wrong.
- **Limited coverage.** Catches structural failures; misses semantic ones.

### Model-graded metrics

A second LLM call scores the output against criteria. Cheap relative to human review, fast, and surprisingly reliable for well-defined criteria. Use it for:

- Faithfulness ("does the answer follow from the retrieved context?")
- Completeness ("does the answer address all parts of the question?")
- Tone / style ("does the answer follow the brand voice?")
- Refusal correctness ("did the agent refuse for the right reason?")

Watch-outs:

- Model-graded metrics drift when you change the grading model. Pin the grader's model and prompt; treat changes as their own deployment.
- A weak grader can rubber-stamp a weak generator. Use a stronger model as the grader than as the generator where possible.
- Grader prompts are themselves prompts — they need their own eval cases.

### Human-graded metrics

Slow, expensive, gold standard. Reserve for:

- Calibrating model-graded metrics (sample 5-10% of model-graded outputs for human review; track agreement rate).
- High-stakes outputs (legal, medical, financial).
- New eval categories where the criteria are still being refined.

Don't try to scale human grading by hiring more graders — scale it by improving the model-graded substitute until human review becomes a calibration sample, not a workflow.

## Online vs offline evals

### Offline evals

Pre-merge, in CI. Catches regressions against the golden dataset before they ship.

- Run on every PR that touches prompts, model selection, retrieval, or tools.
- Hard-fail thresholds for *regressions* (e.g. faithfulness drops > 2 percentage points), not for absolute scores.
- Comment a results table on the PR for reviewer context.

### Online evals

Post-deploy, sampled from production traffic.

- Catches distribution shift the offline suite doesn't model.
- Surfaces patterns that should land in the golden dataset.
- Detects silent regressions caused by upstream model updates.

Use online evals to *find* the cases that belong in offline evals. The two layers feed each other.

## Eval cost budgets

Evals cost LLM calls — sometimes a lot. Sizing the suite is itself an engineering decision.

A rough heuristic:

- **Offline suite, per PR:** 50–500 cases. Costs $1–$50 per PR depending on model size and case complexity.
- **Online sampling, per day:** 1–5% of production traffic. Costs scale with traffic.
- **Human review, calibration:** 50–100 cases per quarter. Costs human time, not LLM tokens.

If your offline suite is too expensive to run on every PR, the problem is usually that the suite is full of cases the cheaper layers (rule-based, smoke tests) should have caught. Tier the suite — quick checks on every PR, full suite on merge to a release branch.

## Regression suites

The single most valuable eval discipline: **every production failure becomes a test case**. When the on-call engineer fixes a bug, the input goes into the golden dataset and the PR is gated on it.

This is how a system stays good. Without it, every fix invites a regression that lands in the next deploy. With it, the system's quality floor only goes up.

Operational rule: a fix without an eval is incomplete. Block the PR.

## The reliability gap (and why cadence matters)

A persistent 2026 finding across enterprise agent deployments: **task-completion benchmarks systematically overestimate production reliability**. Reports place the gap between published benchmark scores and observed production success at ~37 percentage points, with the dominant failure modes being long-horizon brittleness, tool-error compounding, and silent degradation under traffic the benchmark didn't sample.

This is why offline + online evals together are not optional — and why **cadence** is the lever that matters most.

| Eval cadence | Typical detection latency | What it catches |
|---|---|---|
| Per-PR offline suite | Minutes | Direct regressions you authored |
| Daily online sample | Hours | Upstream-model drift, prompt-cache misses, new traffic patterns |
| Weekly full eval cut | Days | Slow drift, long-tail regressions, cumulative behavior change |
| Monthly only | Weeks | Mostly catches catastrophes after customers find them first |

Teams that run their full eval suite weekly report meaningfully fewer production issues than teams running it monthly (one widely-cited 2026 enterprise survey put the reduction at roughly 22%). The direction matters more than the exact number: **the gap between benchmark and production closes with cadence, not with bigger one-time evals**.

Practical consequences:

- Treat single-run benchmark scores (AgentBench, ToolBench, API-Bank) as upper bounds, not targets. Apply a "production discount" when you cite them.
- Include reliability axes the headline benchmarks don't measure: cost efficiency, step efficiency, plan adherence, trace consistency, refusal correctness, abstention rate. See `agent-deployments/docs/cross-cutting/observability.md` for the operational instrumentation that feeds these.
- Long-horizon patterns (`patterns/long_horizon/`) need their own reliability lens — a "task completion rate" that ignores how many resumes a task took hides exactly the reliability gap that matters at scale. Track resumes per task, replan rate, stuck-task rate alongside completion.

If your published metric and your on-call pager tell different stories, the pager is right.

## Where each eval discipline applies, by pattern

| Pattern | Primary eval signal |
|---|---|
| [Prompt Chaining](../patterns/prompt-chaining/overview.md) | Per-step schema validity; end-to-end correctness. |
| [Parallel Calls](../patterns/parallel-calls/overview.md) | Per-branch correctness; aggregation faithfulness. |
| [Orchestrator-Worker](../patterns/orchestrator-worker/overview.md) | Decomposition quality (does the plan cover the task?); worker output quality. |
| [Evaluator-Optimizer](../patterns/evaluator-optimizer/overview.md) | The pattern includes its own evaluator — but that evaluator needs evals too. |
| [ReAct](../patterns/react/overview.md) | Tool-call correctness; iteration count distribution; final answer quality. |
| [Plan & Execute](../patterns/plan_and_execute/overview.md) | Plan quality; per-step execution fidelity. |
| [Tool Use](../primitives/tool_use/overview.md) | Function selection accuracy; argument schema match; refusal of unknown tools. |
| [Memory](../primitives/memory/overview.md) | Retrieval relevance over stored memories; consistency across sessions. |
| [RAG](../patterns/rag/overview.md) | Retrieval recall; faithfulness to retrieved context; citation presence. |
| [Reflection](../patterns/reflection/overview.md) | Critic accuracy; improvement rate per iteration. |
| [Routing](../patterns/routing/overview.md) | Classification accuracy; `unknown`/`escalate` recall. |
| [Multi-Agent](../patterns/multi_agent/overview.md) | Per-agent correctness; cross-agent consistency; orchestration overhead. |
| [Event-Driven](../patterns/event_driven/overview.md) | Idempotency under replay; correctness over event order permutations. |
| [Saga](../patterns/saga/overview.md) | Compensation correctness under simulated failures at each step. |
| [Human in the Loop](../modifiers/human_in_the_loop/overview.md) | Approval-rate signal; correct routing of high-stakes cases to human review. |
| [Long-Horizon](../patterns/long_horizon/overview.md) | Task completion rate AND resumes-per-task; replan rate; stuck-task rate; idempotency under retry. |
| [Agentic RAG](../patterns/agentic_rag/overview.md) | Citation precision; cross-source consistency; abstention rate on out-of-corpus queries. |
| [Sub-agents](../primitives/sub_agents/overview.md) | Per-role schema-result validity; cap-hit rate; tool-grant violations (must be zero). |
| [Guardrails](../modifiers/guardrails/overview.md) | Per-detector FP rate (calibrated); shadow-mode disagreement; bypass-use audit; layer latency. |

## Related

- [Testing Strategies](./testing-strategies.md) — the test pyramid this layer sits in.
- [Hallucination & Grounding](./hallucination-and-grounding.md) — what to evaluate for; abstention is a positive signal, not a failure.
- [Evaluator-Optimizer](../patterns/evaluator-optimizer/overview.md), [Reflection](../patterns/reflection/overview.md) — patterns that embed evaluation as part of generation.
- [Security & Safety](./security-and-safety.md) — adversarial eval cases.

## What this guide deliberately doesn't cover

- Specific eval frameworks (Promptfoo, Inspect, Braintrust, custom). The discipline matters more than the tool.
- Statistical tests for "is this regression significant?" — usually overkill for the sample sizes a team can afford; trend lines and human judgment carry most of the load.
- Per-domain accuracy targets. Those are organizational decisions.
- Comparison evals across models — that's benchmarking, not evals as defined here.
