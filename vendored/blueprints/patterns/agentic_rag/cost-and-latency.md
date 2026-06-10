# Cost & Latency: Agentic RAG

The pattern's compute cost is a multiple of baseline RAG's. Each sub-question pays for retrieval + scoring + reflection; each retry doubles part of that. The win is fewer wrong answers at higher per-question cost. The control knobs that matter most are: per-tier model selection, sub-question caps, and retrieval-attempt caps.

---

## At a Glance

|                                  | Typical (P50)                       | High end (P95)                      |
|----------------------------------|-------------------------------------|-------------------------------------|
| Per-question cost                | $0.02–$0.10                         | $0.50                               |
| Per-question latency             | 2–10s                               | 30s                                 |
| LLM calls per question           | 5–15                                | 30                                  |
| Retrieval calls per question     | 2–6                                 | 15                                  |
| Cost vs baseline RAG             | 3–10×                               | 20×                                 |
| Latency vs baseline RAG          | 2–5×                                | 10×                                 |

Relative cost tier: Medium. Latency tier: Medium-High. The cost is paid per question, every question.

---

## Per-question Cost Breakdown

Each agentic call is itself a tiny pipeline:

| Component | Per-question cost (typical) | Notes |
|---|---|---|
| Decomposition | $0.001–$0.005 | Skipped for simple questions |
| Per-sub-question retrieval | $0.0001 × attempts | Embedding + vector lookup; cheap |
| Per-sub-question relevance scoring | $0.001 × chunks_returned (Haiku) | Cheap per chunk; multiplied by K |
| Per-sub-question sufficiency reflection | $0.003 × attempts (Sonnet) | Modest reasoning |
| Per-sub-question reformulation | $0.003 × (attempts - 1) (Sonnet) | One per retry |
| Cross-source consistency | $0.003 × (sub-questions with multi-source) | When multi-source |
| Answer composition | $0.005–$0.030 (Sonnet/Opus) | Biggest single cost |
| Citation verification | $0.002 (Haiku) | Re-read draft |
| Web / SQL source costs | Variable | External API and DB query costs |

**Concrete (5-sub-question compound query, 2 attempts each, Sonnet/Haiku mix):**
- Decomposition: $0.003
- Retrievals (5 × 2): negligible (embedding + vector)
- Relevance scoring: 5 × 2 × 5 chunks × $0.001 = $0.05
- Reflection: 5 × 2 × $0.003 = $0.03
- Reformulation: 5 × 1 × $0.003 = $0.015
- Cross-source: $0.015
- Composition (Sonnet): $0.020
- Verification: $0.002
- **Total: ~$0.15 per question** (vs ~$0.02 for baseline RAG on the same question — but baseline would only answer 1 of the 5 sub-questions well)

---

## Latency Breakdown

| Component | Typical | Notes |
|---|---|---|
| Decomposition | 200–500ms | One Sonnet call |
| Per retrieval attempt | 50–300ms | Embedding + vector lookup; web search up to 1s |
| Per-chunk relevance scoring | 100–300ms total per attempt | Batched per attempt |
| Per sufficiency reflection | 300–800ms | One Sonnet call |
| Per reformulation | 200–500ms | One Sonnet call |
| Cross-source consistency | 400–800ms | One Sonnet call when needed |
| Composition | 500ms–3s | Depends on output length |
| Verification | 300–600ms | One Haiku call |

A 3-sub-question / 1-attempt average question: ~4–6s end-to-end. A 5-sub-question / 2-attempt heavy question: ~12–20s. Parallel sub-question dispatch can cut wall-clock to ~max(sub-question latencies) at the cost of higher rate-limit pressure.

---

## What Drives Cost Up

- **Over-decomposing.** Each sub-question pays the full per-sub-question stack. Decompose only when truly compound.
- **Loose retry caps.** Each retry adds reflection + reformulation calls. Cap at 3 for cost-sensitive, 5 for high-stakes.
- **High K.** Pulling 20 chunks per retrieval means 20 relevance-scoring calls. K=5 is usually enough; tune against recall measurement.
- **Opus everywhere.** Using Opus for relevance scoring is wasteful — it's a Haiku-class classification task. Tier the loop.
- **Web search per retrieval.** Web APIs have per-call costs; web sources are usually $0.001–$0.01 per query plus possibly per-result-fetch.
- **Composition outputs too long.** A 4000-token answer is rarely better than a 1500-token answer; pay the difference in tokens out.

---

## What Drives Latency Up

- **Sequential sub-question retrieval.** Default is sequential; parallel is much faster when sub-questions are independent.
- **Composition output size.** Longer outputs take longer to stream. Cap output length.
- **Web fetches inside the source adapter.** A search + fetch top-3 results = up to 4 sequential network round-trips per attempt.
- **Reformulation that doesn't improve recall.** When reformulation produces a query that retrieves similar chunks, the next attempt's reflection fires the same insufficient verdict. Cap retries; abstain.
- **Per-tenant rate limits.** A high-volume question dispatcher hits rate limits and serializes; per-question latency grows under load.

---

## Cost & Latency Control Knobs

**Tier the loop.** The single biggest lever. Decomposition (Sonnet), source routing (Haiku), relevance scoring (Haiku), reflection (Sonnet), composition (Sonnet/Opus), verification (Haiku). The total cost can be 2–3× lower than a single-model implementation.

**Skip decomposition for simple questions.** A classifier (Haiku) decides "is this compound?" — if not, skip straight to retrieval. Cuts cost by 30% on simple-question traffic.

**Cap retries explicitly per sub-question.** 3 attempts default; 5 for high-stakes domains; 2 for the cheapest tier.

**Parallel sub-question dispatch when independent.** When sub-questions don't depend on each other (and don't share rate budget), fan out. Wall-clock drops to the slowest sub-question.

**Cache successful (sub-question, source) routings.** Many similar questions reuse the same routing. Cache for warm queries.

**Cache scored chunks per (query, source) for identical retries.** Re-scoring the same chunks burns Haiku calls; the score function is mostly deterministic.

**Tighter top-K for low-recall sources.** Pull K=3 instead of K=10 when the source is reliable; pull K=10 when broad sweep matters.

**Aggressive abstention for low-confidence.** Abstaining costs less than composing a wrong answer plus the operational cost of the wrong answer. Set the bar high.

**Pre-summarize web chunks via the quarantined LLM.** Cuts composition input tokens and improves grounding precision.

---

## Comparison to Related Patterns

| Pattern | Est. LLM calls per question | Est. cost per question | Best when |
|---|---|---|---|
| Baseline RAG | 1 | $0.005–$0.02 | Single source, simple questions, high recall |
| Plain ReAct over a knowledge base | 5–20 | $0.05–$0.30 | The agent decides what tool / step; little retrieval discipline |
| Plan & Execute over RAG | 5–10 | $0.04–$0.20 | Plan-then-execute structure works for the domain |
| Agentic RAG | 5–30 | $0.02–$0.50 | Multi-source, multi-hop, citation-required |
| Agentic RAG + Sub-agents | 10–60 | $0.05–$1.00 | Heavy sub-questions worth their own context window |

The distinctive cost shape: **agentic RAG trades cost for *correctness rate*, not for raw throughput**. The right metric is `(cost per question) × (1 / correctness rate)`. A 3× cost increase that doubles correctness is a win. A 3× cost increase that adds 5% correctness is not.
