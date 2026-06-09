# Hallucination & Grounding

Agents are statistical text generators. Without explicit grounding, they will confidently produce plausible-but-wrong output — including invented tool arguments, citations to non-existent sources, and answers to questions whose premises the user got wrong. This doc names the patterns that reduce hallucination in production and the patterns that let an agent admit it doesn't know.

## Why agents hallucinate

Three mechanisms account for most production hallucinations:

1. **Distribution shift.** The model encounters terminology, schemas, or domain context underrepresented in training. It fills the gap with the closest neighbor it has.
2. **Tool-output overconfidence.** A tool returns ambiguous, partial, or stale data. The model integrates it as authoritative because the prompt frames tool outputs as ground truth.
3. **Multi-step context loss.** In long-running agent loops, earlier reasoning slips out of attention. The agent rederives a conclusion from a partial view of the history and contradicts itself.

These aren't bugs in the model — they're properties of next-token generation under uncertainty. Grounding doesn't eliminate them; it constrains where they can land.

## Grounding strategies

### Retrieval grounding

Inject task-relevant facts via retrieval before generation. The agent answers from retrieved context, not from parametric memory. See [RAG](../patterns/rag/overview.md) for the structural pattern; what matters for hallucination:

- **Cite or refuse.** If the model can't ground a claim in retrieved text, it shouldn't make the claim. Output schemas that *require* citations make this enforceable.
- **Retrieval quality is the ceiling.** If retrieval misses or returns the wrong chunk, the generation can't recover. Eval retrieval recall, not just end-to-end answer quality.
- **Show, don't tell.** Pass retrieved chunks verbatim with source IDs. Don't summarize before passing. Summarization is another generation step that can hallucinate.

### Schema-bounded outputs

Force structured outputs validated against a schema. Free prose has unlimited surface for invention; a typed schema constrains the model to fields you control.

- For tool calls, function-calling APIs with strict JSON schemas catch invented parameter names and types at the protocol layer.
- For final answers, force a schema that includes a `confidence` or `unknown` field. An agent that can output `unknown` will use it; an agent that must produce prose will fabricate.
- Pair schemas with allow-listed enumerations for high-stakes fields (intents, categories, action verbs).

### Allow-listed enumerations

When an output drives downstream code (a router decision, a workflow step, a database write), the value should come from an enumeration the agent picks from — not from text it generates. This is the difference between *"What category is this?"* (open-ended, hallucinable) and *"Which of [billing, technical, account] best matches?"* (constrained, auditable).

### Tool-output validation

Tool outputs are external inputs that the model treats as facts. Validate them before re-feeding:

- Schema-check structured returns.
- Sanity-check numeric ranges (a "user age: 487" return is a bug or attack).
- Tag with provenance ("from: stripe API at 14:02 UTC") so the model can reason about freshness.

### Model-graded self-checks

After generation, ask a second LLM call (or the same model with a different prompt) to evaluate the answer against the source material: *"Given these retrieved chunks, is the following claim supported? Answer YES, NO, or PARTIAL with the supporting span."* See [Reflection](../patterns/reflection/overview.md) for the structural pattern.

This adds latency and cost. Use it where the failure mode warrants the budget — high-stakes outputs, customer-facing summaries, anything that ships to production unattended.

## Abstention patterns

An agent that can say *"I don't know"* is more useful than one that always answers. Abstention requires designing for it explicitly.

### Confidence thresholds

If the model exposes a logprob or self-reported confidence, gate the final answer on it. Below threshold → return *"I'm not confident; here's what I tried and where I got stuck"*, escalate, or invoke a fallback.

Pure self-reported confidence is unreliable; combine with structural signals (retrieval matched zero chunks above similarity threshold, the planner failed to generate a coherent plan, the tool returned an error).

### "I don't know" routing

For classification-style outputs, include an explicit `unknown` class in the enumeration. Train (or prompt-instruct) the model to prefer it over guessing. The downstream system handles `unknown` by escalating, asking a clarifying question, or invoking a stronger model — see [routing](../patterns/routing/overview.md).

### Escalation to a human

The natural terminator for an uncertain agent is a human review queue, not a confident fabricated answer. See [Human in the Loop](../patterns/human_in_the_loop/overview.md). The HITL pattern is purpose-built for *"propose, wait for approval, commit"* — that flow IS the abstention mechanism for high-stakes actions.

### Refuse-list

For domains where the agent should *never* answer (medical advice, legal opinions, financial decisions outside scope), maintain a refuse-list of input patterns or topics. Detected → route to a "this is out of scope; here's where to go instead" handler.

## Eval-gated deployment

Hallucination is hard to spot in production because the failure mode is *plausible*. The only durable defense is an eval suite that includes adversarial cases and runs on every change.

- **Golden datasets** of input → expected behavior, including expected `unknown` outputs and refusals.
- **Regression suites** — every production hallucination becomes a test case.
- **Online vs offline evals.** Offline (pre-merge) catches regressions at CI time; online (post-deploy, sampled) catches drift the offline suite doesn't model.

See [Evals & Quality](./evals-and-quality.md) for the longer treatment of how to build and maintain these.

## Where each grounding strategy applies, by pattern

| Pattern | Primary grounding lever |
|---|---|
| [Prompt Chaining](../workflows/prompt-chaining/overview.md) | Schema-bounded outputs at each gate; validation between steps. |
| [Parallel Calls](../workflows/parallel-calls/overview.md) | Schema-bounded outputs; aggregator validates cross-call consistency. |
| [Orchestrator-Worker](../workflows/orchestrator-worker/overview.md) | Worker outputs schema-validated before orchestrator integrates. |
| [Evaluator-Optimizer](../workflows/evaluator-optimizer/overview.md) | The pattern *is* a grounding mechanism — but the evaluator's own outputs need grounding. |
| [ReAct](../patterns/react/overview.md) | Tool-output validation; iteration caps; abstention via `unknown` action. |
| [Plan & Execute](../patterns/plan_and_execute/overview.md) | Plan validated against an allow-listed action set; per-step grounding. |
| [Tool Use](../patterns/tool_use/overview.md) | Schema-bounded tool calls; tool-output validation; allow-listed function set. |
| [Memory](../patterns/memory/overview.md) | Provenance tags on stored memories; retrieval grounded over memory. |
| [RAG](../patterns/rag/overview.md) | Retrieval grounding (the headline mechanism); citation enforcement; cite-or-refuse. |
| [Reflection](../patterns/reflection/overview.md) | Model-graded self-check (the pattern itself); requires its own grounding for the critic. |
| [Routing](../patterns/routing/overview.md) | Allow-listed enumeration of routes; explicit `unknown`/`escalate` path. |
| [Multi-Agent](../patterns/multi_agent/overview.md) | Per-agent grounding plus cross-agent consistency checks. |
| [Event-Driven](../patterns/event_driven/overview.md) | Schema-validated event payloads; idempotency keys carry provenance. |
| [Saga](../patterns/saga/overview.md) | Saga log carries provenance; compensation triggered by validated state. |
| [Human in the Loop](../patterns/human_in_the_loop/overview.md) | Human is the grounding mechanism for the gated action. |

## Related

- [Security & Safety](./security-and-safety.md) — indirect prompt injection is hallucination's adversarial cousin; the defenses overlap.
- [Evals & Quality](./evals-and-quality.md) — what makes a hallucination test suite real.
- [RAG](../patterns/rag/overview.md), [Reflection](../patterns/reflection/overview.md), [Human in the Loop](../patterns/human_in_the_loop/overview.md) — the three structural patterns most often deployed against hallucination.

## What this guide deliberately doesn't cover

- Specific benchmarks (HaluEval, TruthfulQA). Useful for research; not actionable as a per-deployment checklist.
- Vendor-specific "hallucination rate" claims — they're not comparable across labs and rarely hold up in production.
- RLHF, fine-tuning, or post-training mitigation. Out of scope for an architecture-layer doc.
- Per-domain accuracy thresholds. Those are organizational decisions.
