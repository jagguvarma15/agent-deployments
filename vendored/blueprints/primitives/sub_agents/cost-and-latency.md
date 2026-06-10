# Cost & Latency: Sub-agents

The primitive's cost shape is straightforward: each sub-agent invocation is its own agent loop. Cost goes up linearly with sub-agent count; latency depends on whether they run in parallel. The wins come from two places — keeping the parent's context window small, and using cheaper models for sub-tasks.

---

## At a Glance

|                                  | Typical (P50)                        | High end (P95)                       |
|----------------------------------|--------------------------------------|--------------------------------------|
| Spawn overhead                   | ~150ms                               | 500ms                                |
| Per sub-agent compute cost       | $0.001–$0.05 (model-dependent)       | $0.20                                |
| Parallel speedup (3 sub-agents)  | ~2.5×                                | ~3× (independent tasks)             |
| Token spend ratio (vs single agent on same task) | 0.7×–1.3× (often *lower* due to model mix) | 1.5×                                 |
| Parent's context window savings  | 30–80% smaller transcript            | 90%                                  |

Sub-agents are a **context lever** before they're a cost lever. The parent's context stays small even when total work grows.

---

## Per-sub-agent Cost Breakdown

The per-spawn cost is the standard agent-loop cost:

| Component | Source | Typical $ per spawn |
|---|---|---|
| System prompt + task | One model call (cached prefix on most providers) | $0.0005 |
| Per-step reasoning | N model calls inside the sub-agent's loop | $0.001 × steps |
| Tool calls | Per-tool cost (usually paid APIs) | Variable |
| Result emission + schema validate | One model call + a parser pass | $0.0005 |
| Audit emission | DB write | < $0.00001 |

For a 6-step research sub-agent on Sonnet with 4 search calls (each $0.001): ~$0.015 per sub-agent. The same task on a single Opus parent agent: $0.030–$0.060 (the parent reads the full search output). **Sub-agent cost ≈ half the equivalent single-agent cost when you can drop a model tier.**

---

## Parallel Speedup Math

Three independent sub-agents in parallel, each taking 12s wall-clock:

- Sequential: 36s.
- Parallel (no shared bottleneck): 12s + overhead = ~14s. **2.5× speedup.**
- Parallel with rate-limit bottleneck on the shared model: bounded by per-tenant rate limit. May degrade to 18s.

Amdahl's law applies: if 30% of the parent's work isn't parallelizable, max speedup is 3.3× regardless of how many sub-agents fan out. Measure the serial portion before promising linear speedup.

---

## What Drives Cost Up

- **Over-spawning.** Spawning a sub-agent for a task one tool call would have done. Every spawn has a fixed overhead; trivial tasks don't justify it.
- **No per-role model selection.** Running every sub-agent on the parent's model (often Opus) wastes the cost savings. Use Sonnet/Haiku for distillation-only roles.
- **Failed schema validation re-prompts.** Each re-prompt is an extra model call. Schema-error rates over 2% cost real money; tighten the prompt or loosen the schema.
- **Long transcripts inside sub-agents.** A sub-agent with `max_steps=20` and no compaction will hit cap regularly with growing tokens. Cap compaction inside the sub-agent OR drop `max_steps`.
- **Deep recursion.** Each level of recursion adds spawn overhead and doubles the audit volume. Cap depth at 2–3.

---

## What Drives Latency Up

- **Sequential spawn.** Awaiting one sub-agent before spawning the next adds their durations together. Parallel where possible.
- **Slowest sub-agent in parallel.** The fan-out's wall-clock equals the slowest sub-agent's duration. One slow role becomes the tail. Either speed it up (model swap, smaller task) or tighten its deadline and accept more partials.
- **Rate-limit serialization.** Many parallel sub-agents on the same model hit the per-tenant rate limit and serialize internally. Cap parent concurrency to your rate budget.
- **Spawn overhead.** ~150ms per spawn. For trivially-cheap sub-agents, the overhead can exceed the work.
- **Result schema retries.** Each retry is one more model round-trip per failed sub-agent.

---

## Cost & Latency Control Knobs

**Per-role model selection.** The single biggest lever. The planner is Opus, the workers are Sonnet, the formatter is Haiku. Often the total token spend drops even as the total step count rises.

**Tighter result schemas.** Force the sub-agent to emit a small structured result instead of a verbose explanation. Cuts output tokens 5–10×; sub-agent transcript stays full but the parent's context stays tight.

**Parallel by default for independent tasks.** Sequential is the wrong default in 2026. Use `asyncio.gather` (or framework equivalent) and let the scheduler handle concurrency.

**Per-role deadlines.** Hard caps prevent runaway sub-agents. Set the deadline to ~1.5× the role's P95 duration; tail cases get capped, normal traffic doesn't.

**Cache the role's system prompt.** Almost every provider supports prefix caching. Long `ROLE.md` files pay back fast — every spawn after the first hits the cache.

**Limit recursion depth.** Depth 2 covers 95% of legitimate cases. Depth 3 is exceptional and should require a comment. Depth 4 is a bug.

**Concurrency cap at the parent.** Don't spawn 30 sub-agents in parallel; you'll hit rate limits and the slowdown defeats the parallelism. Cap at 4–8 unless you have measured headroom.

**Pre-allocate per-role scratch directories.** Parallel sub-agents fighting for the same filesystem path is the most common coordination bug. Per-role dirs are free and prevent it.

---

## Comparison to Related Patterns

| Pattern / Primitive | Est. cost overhead vs single agent | Est. latency vs single agent | Best when |
|---|---|---|---|
| Tool Use (chunky tool, big return) | Baseline | Baseline | Tool's output is small enough not to bloat context |
| Sub-agents (sequential) | 0.7×–1.0× (model mix savings) | 1.0× (same as serial) | Task decomposes; main agent's context matters |
| Sub-agents (parallel) | 0.7×–1.0× | 0.3×–0.5× | Independent sub-tasks, latency-sensitive |
| Multi-Agent pattern | 1.0×–1.5× | 0.5×–1.0× | Sub-agents need to coordinate via more than handoffs |

The distinctive cost shape: **sub-agents almost always lower the parent's context spend, often lower total spend via model mixing, and unlock parallel latency wins**. The overhead is the per-spawn cost — keep that overhead amortized across enough sub-agent work to make the spawn worth it.
