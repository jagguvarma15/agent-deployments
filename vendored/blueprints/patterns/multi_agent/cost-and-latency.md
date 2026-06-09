# Cost & Latency: Multi-Agent

All figures are rough estimates based on a frontier-tier model at approximately
$3/1M input tokens and $15/1M output tokens. Multi-Agent is the most expensive
pattern in this library. Its cost depends on the number of agents, rounds, and the
complexity of each sub-agent.

---

## At a Glance

|                          | Typical (P50 estimate)           | High end (P95 estimate)               |
|--------------------------|----------------------------------|---------------------------------------|
| LLM calls per request    | ~8 - 15 (2 rounds x 3 agents)   | ~25+ (4 rounds x 4+ agents)           |
| Total input tokens       | ~8,000 - 20,000                  | ~40,000+                              |
| Total output tokens      | ~2,000 - 6,000                   | ~12,000+                              |
| Latency                  | ~8 - 20s                         | ~30 - 60s+                            |
| Cost per 1,000 requests  | ~$10 - $25                       | ~$50 - $120                           |

Relative cost tier: High. Multi-Agent multiplies the cost of every sub-agent by the
number of delegations. Misuse of this pattern for tasks that a single ReAct agent
could handle is the most common source of unexpectedly high LLM bills.

---

## Call Breakdown

| Call                    | Purpose                              | Est. input tokens | Est. output tokens |
|-------------------------|--------------------------------------|-------------------|--------------------|
| Supervisor decide (x R) | Plan delegations for round R         | 500 - 1,500 each  | 100 - 300 each     |
| Agent A run             | Sub-agent completes its task         | 500 - 3,000+      | 200 - 1,000+       |
| Agent B run             | Sub-agent completes its task         | 500 - 3,000+      | 200 - 1,000+       |
| Agent N run             | Sub-agent completes its task         | 500 - 3,000+      | 200 - 1,000+       |
| Synthesize              | Combine all agent outputs            | 1,000 - 5,000+    | 300 - 1,000        |

Each sub-agent call may itself be a ReAct loop, RAG pipeline, or Reflection loop.
If an agent is a 5-step ReAct loop, it contributes 5 LLM calls plus tool calls to
the total, not just 1.

Supervisor context growth: each round the supervisor receives the accumulated outputs
of all prior agents. By round 3 with verbose agents, the supervisor input can exceed
5,000 tokens before any instructions are added.

---

## Latency Profile

Sequential agent execution (default):
Latency = sum(supervisor rounds x supervisor call) + sum(all agent run times) + synthesize

With parallel agent execution within a round:
Latency = sum(supervisor rounds x supervisor call) + sum(max agent in each round) + synthesize

P50 estimate (2 rounds, 3 sequential agents, moderate complexity): ~8 - 20s
P95 estimate (4 rounds, 4 agents, complex sub-agents): ~30 - 60s
With parallel agents within rounds: P50 drops to roughly ~5 - 12s

---

## What Drives Cost Up

- Number of agents called. Each delegation is at minimum one LLM call. Sub-agents
  that are themselves loops (ReAct, Reflection) multiply this.
- Number of supervisor rounds. Each round adds a full supervisor decide call plus
  all delegated agent calls. Without a round cap, the supervisor may re-delegate
  unnecessarily.
- Agent verbosity. Each agent's output is accumulated into the supervisor's context
  for subsequent rounds and into the synthesis input. Verbose agents create a
  compounding token cost.
- Sub-agent complexity. A sub-agent that runs a 5-step ReAct loop costs as much as
  a standalone ReAct call. Multi-Agent multiplies this by agent count.
- Synthesis input size. All agent outputs are concatenated for synthesis. If 4 agents
  each produce 800 tokens, the synthesis input starts at 3,200 tokens before any
  prompt instructions.

---

## What Drives Latency Up

- Sequential agent execution (sum of all agent latencies vs max)
- Round count (each round is sequential)
- Complex sub-agents (ReAct loops, Reflection loops inside agents add their own latency)
- Large synthesis context (slow final call)

---

## Cost Control Knobs

Verify you actually need Multi-Agent. A single ReAct agent with multiple tools can
handle many tasks at 1/5 to 1/10 the cost. Only use Multi-Agent when tasks genuinely
require parallel specialization or when sub-tasks are too complex for a single agent
to interleave.

Cap rounds and agent count explicitly. Set max_rounds=3 and limit the number of
registered agents. Unconstrained, the supervisor may call 6 agents over 4 rounds on
a task that needed 2 agents over 2 rounds.

Constrain sub-agent output length. Every 100 tokens of sub-agent output reduction
saves those tokens in every subsequent supervisor call and in the final synthesis.
Add output length constraints to every sub-agent's system prompt.

Run agents in parallel within each round. When the supervisor delegates to agents
A and B in the same round and they are independent, run them concurrently. This halves
the latency contribution of that round with no change in cost.

Use cheaper models for routine sub-agents. A summarization agent, extraction agent,
or formatting agent does not need a frontier model. Use a cheaper, faster model for
those roles and reserve the most capable model for the supervisor and agents requiring
complex reasoning.

Cap synthesis input. Before calling the synthesizer, summarize each agent's output
to its key points. Passing a 200-token summary per agent vs the raw 800-token output
reduces synthesis input by 75% with minimal information loss.

---

## Comparison to Related Patterns

| Pattern             | Est. LLM calls   | Est. cost tier | Est. latency | Best when                                      |
|---------------------|------------------|----------------|--------------|------------------------------------------------|
| Multi-Agent         | 8-25+ (very high)| High           | Very High    | Parallel specialization genuinely required     |
| Orchestrator-Worker | 2+N (medium)     | Medium to High | Medium       | Dynamic decomposition, no autonomous sub-agents|
| ReAct               | 3-10 (medium)    | Medium         | Variable     | Single agent, multi-step tool use              |
| Plan & Execute      | 1+N (medium)     | Medium         | Medium       | Ordered steps, no parallel agent needed        |
