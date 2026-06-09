# Cost & Latency: ReAct Agent

All figures are rough estimates based on a frontier-tier model at approximately
$3/1M input tokens and $15/1M output tokens. ReAct has the highest variance of
any single-agent pattern because step count is determined at runtime.

---

## At a Glance

|                          | Typical (P50 estimate) | High end (P95 estimate)               |
|--------------------------|------------------------|---------------------------------------|
| LLM calls per request    | ~3 - 5                 | ~8 - 10 (near max_steps)              |
| Total input tokens       | ~2,000 - 6,000         | ~15,000+                              |
| Total output tokens      | ~400 - 1,200           | ~2,500+                               |
| Latency                  | ~2 - 5s                | ~8 - 20s                              |
| Cost per 1,000 requests  | ~$1.50 - $5.00         | ~$10 - $30                            |

Relative cost tier: Medium, but highly variable. A well-tuned ReAct agent on simple
tasks is cheap. An unconstrained agent on complex tasks can approach the cost of a
Multi-Agent system.

---

## Call Breakdown

| Call            | Purpose                           | Est. input tokens           | Est. output tokens |
|-----------------|-----------------------------------|-----------------------------|--------------------|
| Step 1          | First think + act                 | ~500 - 1,000                | ~80 - 200          |
| Step N          | Think + act (context grows)       | ~500 + ~300 per prior step  | ~80 - 200          |
| Final step      | Final answer                      | Largest context in the run  | ~100 - 500         |
| Tool call       | External execution (not LLM)      | N/A                         | N/A                |

Context accumulation is the defining cost characteristic of ReAct. Every step appends
a thought, action, and observation to the message history. By step 6, the input context
can be 4,000+ tokens even if each individual step is small.

Rough context growth estimate:
- Step 1: ~600 input tokens
- Step 3: ~1,500 input tokens
- Step 5: ~2,800 input tokens
- Step 8: ~5,000+ input tokens

---

## Latency Profile

Latency = sum of (LLM call latency + tool call latency) per step.

Tool latency varies enormously by tool type:
- Web search API: ~200 - 1,500ms
- Database query: ~50 - 300ms
- Code execution: ~500 - 5,000ms
- Calculator / local function: under 10ms

P50 estimate (3 steps, moderate tool latency): ~2 - 5s
P95 estimate (7-8 steps, one slow tool): ~8 - 20s

There is no parallelism in standard ReAct. Every step is sequential.

---

## What Drives Cost Up

- Step count. The primary cost driver. Each step adds a full LLM call with a growing
  context. Going from 3 steps to 6 steps roughly triples the token cost because both
  call count and context size increase.
- Context accumulation. Unlike Prompt Chaining, where context is reset each step,
  ReAct carries the full history. A 10-step run can have 6,000+ input tokens on the
  final call alone.
- Verbose tool observations. A tool that returns a 2,000-word web page adds 2,000
  tokens to every subsequent step's context. Tool outputs should be truncated or
  summarized before being added to history.
- Repeated tool calls with the same input. A loop where the agent calls search("X")
  multiple times wastes tokens and latency on identical operations.

---

## What Drives Latency Up

- Step count (strictly sequential)
- External tool latency (especially web search, code execution, external APIs)
- Large context on later steps (more tokens to process per call)
- max_steps guard triggering: if the agent reaches max steps, you've paid for all
  of them at near-maximum context size

---

## Cost Control Knobs

Set max_steps at the lowest value that reliably handles your task. For most tasks,
3-5 steps is sufficient. max_steps=10 is a common default but is rarely needed for
well-scoped tasks.

Truncate or summarize tool observations before adding them to history. A web search
returning a full article can be summarized to 3-5 key sentences. This is the highest
single-call cost reduction available in ReAct.

Implement history pruning. Keep only the last N steps in the message history, or
summarize older steps into a running "what I've found so far" block. This prevents
context growth from compounding across many steps.

Detect and short-circuit repeated tool calls. If the same tool is called with the same
input twice in one run, inject a message: "You have already called this tool with this
input. Use a different approach." This costs nothing and prevents loops.

Use a cheaper model for simple tool-use steps. If step 3 is clearly just "call the
calculator with these numbers," a cheap model handles it well. Reserve the most capable
model for steps that require complex reasoning.

---

## Comparison to Related Patterns

| Pattern         | Est. LLM calls     | Est. cost tier    | Est. latency | Best when                                     |
|-----------------|--------------------|--------------------|--------------|-----------------------------------------------|
| ReAct           | 3 - 10+ (dynamic) | Medium, high var.  | Variable     | Open-ended tasks, steps unknown upfront       |
| Tool Use        | 1 - 5 (low)       | Low to Medium      | Low          | Structured tool calls, 1-2 tools per request  |
| Plan & Execute  | 1+N (fixed plan)  | Medium             | Medium       | Complex tasks needing upfront structure       |
