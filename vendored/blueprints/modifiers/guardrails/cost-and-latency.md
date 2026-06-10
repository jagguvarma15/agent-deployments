# Cost & Latency: Guardrails

The modifier's compute cost is dominated by two things: the cheap detectors (regex, schema, allow-list) that add tens of milliseconds each, and the quarantined LLM call that adds one extra model invocation per untrusted tool result. The latency tax depends on which layers you enable and how many detectors run per layer.

---

## At a Glance

|                                  | Typical (P50)                       | High end (P95)                      |
|----------------------------------|-------------------------------------|-------------------------------------|
| Latency added (input + output)   | 60–200ms                            | 400–800ms                           |
| Latency added per tool call (tool layer)  | 5–20ms                     | 50ms                                |
| Quarantined LLM call             | 200–600ms (Haiku-class)             | 1.5s                                |
| Compute cost per guarded request | < $0.001 in detectors              | < $0.01                             |
| Quarantined LLM cost per untrusted tool call | $0.001–$0.005           | $0.02                               |
| Net cost increase vs unguarded   | 5–25% (depends on tool-call density) | 50% (tool-heavy with dual-LLM)     |

Relative cost tier: Low-Medium (matches `metadata.json`). Latency tier: Medium — the dominant tax is the quarantined LLM call on tool-heavy workflows.

---

## Per-Layer Latency Breakdown

| Layer | Detector class | Typical | Notes |
|---|---|---|---|
| Input | Allow-list / length cap | < 1ms | Set per detector; budget enforced in CI |
| Input | PII regex | 5–20ms | Linear in input length |
| Input | Injection classifier (small model) | 50–200ms | The biggest single input-layer cost |
| Input | Embedding-based jailbreak match | 50–100ms | Vector lookup |
| Tool | Allow-list + schema | < 5ms | Per tool call |
| Tool | Rate-budget check | < 1ms | Counter |
| Tool | Authorization (RBAC / OPA) | 5–20ms | Network round-trip if external |
| Output | Schema validation | 1–5ms | Per draft |
| Output | PII / secret leak | 5–50ms | Linear in output length |
| Output | Toxicity classifier | 50–200ms | Optional |
| Output | Faithfulness re-prompt | 200–600ms | Extra LLM call |

A reasonable production budget: 100ms for input layer, 20ms per tool call for tool layer, 50ms for output layer (without faithfulness re-prompt). With faithfulness re-prompt enabled, output budget jumps to ~500ms.

---

## Quarantined LLM Cost Shape

This is the cost item most teams underestimate. Dual-LLM means every untrusted tool result gets a second LLM call to summarize it.

| Workload | Quarantined-LLM call density | Cost impact |
|---|---|---|
| No tools, only chat | 0 calls / request | None |
| One web-search per request | 1 call / request | +1 small-model call cost |
| ReAct loop with 5 search calls | 5 calls / request | +5 small-model call costs |
| RAG with 8 retrieved chunks | 1 call (batched summary) / request | +1 small-model call |
| Multi-agent with 3 sub-agents each doing 4 searches | 12 calls / request | +12 small-model call costs |

**Concrete:** A Sonnet ReAct agent that did $0.02 per request unguarded becomes ~$0.024 per request guarded with 4 untrusted tool calls and Haiku-quarantined summarization. ~20% cost increase, 99% of indirect-injection paths closed.

**When dual-LLM cost is unacceptable:**

- Tools are deterministic and return structured data the actor would receive as data anyway (calculator, database queries, in-house APIs you control). Mark them `trusted=true`.
- The agent's tool budget is already > 10 calls per request. The dual-LLM cost dominates everything else; consider a single batched summary at the end of a sub-task instead of per-tool summaries.

---

## What Drives Cost Up

- **Untuned tool trust.** If every tool is marked untrusted by default, every tool result triggers a quarantined call. Audit your tool registry; mark trusted ones explicitly.
- **Faithfulness re-prompts.** Each faithfulness check is a full LLM call against the draft answer + retrieved docs. Useful for high-stakes RAG but a big latency tax. Use on output classes that justify it.
- **Expensive detectors on cheap classes.** Running a toxicity classifier on routine internal traffic is wasted spend. Per-tenant policy lets you skip layers for low-risk classes.
- **Detector model upgrades.** A move from a small classifier to a large one doubles the cost of every check. Calibrate against the FP rate, not just headline accuracy.
- **Output regenerates (rewrite loop).** Each rewrite re-runs the actor model + the output layer. A rewrite rate over 5% means the modifier is doing the agent's job; tune the agent prompt instead.

---

## What Drives Latency Up

- **Sequential detectors with no short-circuit.** If three classifiers can each block, run them in cost order; first block exits.
- **Synchronous quarantined call inside a parallel agent loop.** The dual-LLM call adds latency only on the critical path; if the actor can do unrelated work while the quarantine runs, pipeline them.
- **Network gateway adds round-trip latency.** In-process gateway is faster; out-of-process is more maintainable. Choose based on traffic volume.
- **Large input or output.** PII / secret regex is linear in length. Cap input length at the input layer, output length in the agent prompt.

---

## Cost & Latency Control Knobs

**Mark trusted tools explicitly.** Default to untrusted, but a clear `trusted=true` flag for in-house tools that return structured data skips the quarantined call.

**Batch quarantined summarization.** If the actor makes 4 retrieval calls in a row, batch them into one summarization call at the end of the sub-task. Cost cut by 75% with no semantic loss.

**Per-tenant detector enablement.** A trusted enterprise tenant doesn't need the same input-layer surface as an open-internet endpoint. Policy-as-data makes this a config change.

**Use a smaller quarantined model than the actor.** The quarantined LLM is doing extract-not-decide. Haiku is fine for almost all cases; Opus is overkill.

**Cache structured tool-output summaries.** When a tool returns deterministically-keyed content (search results for the same query, retrieved chunks for the same doc id), cache the quarantined summary alongside the tool result.

**Disable optional output detectors per output class.** Faithfulness re-prompts only on high-stakes outputs. Toxicity on user-facing only; skip on internal automation.

**Promotion gate on shadow-mode FP rate.** Detectors stay in shadow mode until measured FP rate is under target. Avoids the "we deployed a new detector and blocked 5% of legitimate traffic" incident.

---

## Comparison to Related Patterns

| Pattern / Modifier | Est. cost overhead | Est. latency overhead | Best when |
|---|---|---|---|
| Plain Tool Use | 0% | 0ms | Trusted environment |
| Tool Use + inline filters | 1–5% | 5–20ms | Single-team dev workflow |
| Guardrails (no dual-LLM) | 5–10% | 60–200ms | Trusted tool sources |
| Guardrails (with dual-LLM) | 15–30% | 200–800ms | Untrusted tool sources, customer-facing |
| Guardrails + HITL | Same as Guardrails + human time | Same + human latency | Highest-stakes mutations |

The distinctive cost shape of Guardrails: **the cost is paid per request, every request**. Unlike HITL (cost only when the gate fires), Guardrails runs every layer every time. That's the price of defense in depth — make the layers cheap by selecting calibrated detectors and using a small quarantined model.
