# Cost & Latency: Tool Use

All figures are rough estimates based on a frontier-tier model at approximately
$3/1M input tokens and $15/1M output tokens. Tool Use is one of the cheapest
agent patterns when scoped to 1-2 tools per request.

---

## At a Glance

|                          | Typical (P50 estimate) | High end (P95 estimate)              |
|--------------------------|------------------------|--------------------------------------|
| LLM calls per request    | ~2 (1 tool call + final)| ~6 (multi-turn, 3 tool calls)       |
| Total input tokens       | ~600 - 2,000           | ~4,000+                              |
| Total output tokens      | ~100 - 400             | ~800+                                |
| Latency                  | ~0.8 - 2s              | ~3 - 6s                              |
| Cost per 1,000 requests  | ~$0.40 - $1.50         | ~$3 - $8                             |

Relative cost tier: Low to Medium. Single-tool-call requests are among the cheapest
in the agent pattern library. Cost scales with the number of tool call rounds.

---

## Call Breakdown

| Call                   | Purpose                                  | Est. input tokens | Est. output tokens |
|------------------------|------------------------------------------|-------------------|--------------------|
| LLM call (initial)     | Decide which tool to call and with what  | 300 - 800         | 50 - 150           |
| Tool execution         | External function (not LLM cost)         | N/A               | N/A                |
| LLM call (with result) | Generate response using tool output      | 400 - 1,200       | 100 - 400          |
| Additional rounds      | If multi-tool calls needed               | +300 - 600 each   | +50 - 150 each     |

Tool execution cost is not an LLM cost but does add to latency. API calls,
database queries, and code execution vary from under 10ms to several seconds.

---

## Latency Profile

For a single tool call:
- First LLM call (decide): ~300 - 600ms
- Tool execution: ~50 - 2,000ms (highly tool-dependent)
- Second LLM call (respond): ~300 - 700ms

P50 estimate (1 tool call, fast tool): ~0.8 - 2s
P95 estimate (3 tool calls, one slow tool): ~3 - 6s

The tool execution latency often dominates total latency for fast LLMs but slow tools
(e.g., web search, code execution). For fast tools (local function, cache lookup),
the LLM calls dominate.

---

## What Drives Cost Up

- Number of tool call rounds. Each round adds 2 LLM calls (one to decide, one to respond)
  plus the tool execution. Going from 1 round to 3 rounds roughly triples the LLM cost.
- Tool result size. A tool that returns a 1,500-token response adds 1,500 tokens to
  the next LLM call's input. Web search results and database query results are common
  sources of large tool outputs.
- Schema size. Every LLM call that includes tool schemas pays for those schemas as
  input tokens. 5 tools with detailed schemas can add 800-1,500 tokens to every call.
- Verbose system prompt. Added to every round; pays for itself multiple times in a
  multi-turn tool use session.

---

## What Drives Latency Up

- Slow external tools (web search, code execution, external APIs)
- Multi-turn tool calls (each round is sequential)
- Large tool result injection (large inputs slow generation)

---

## Cost Control Knobs

Include only the tools needed for the current task. Do not pass all registered tools
to every call. If the request is clearly a data lookup, exclude file-write and email
tools. Fewer schemas = fewer input tokens per call.

Truncate tool results before injection. A database query returning 50 rows may only
need the top 5 to answer the question. Add a truncation step in the dispatcher that
summarizes or limits large tool outputs.

Cache tool results for identical inputs. If the same tool is called with the same
arguments within a session, return the cached result. This eliminates the tool call
latency and, more importantly, avoids paying for the same result injection multiple times.

Use a cheaper model when tool schemas are simple and the task is mechanical. The LLM
only needs to map the user request to the right function name and arguments. A smaller,
faster model often does this as reliably as a frontier model.

Batch reads. If the task requires reading 5 files, try to include them in a single
"read multiple files" tool call rather than 5 separate single-file calls. Fewer
rounds = fewer LLM calls.

---

## Comparison to Related Patterns

| Pattern     | Est. LLM calls    | Est. cost tier | Est. latency | Best when                                   |
|-------------|-------------------|----------------|--------------|---------------------------------------------|
| Tool Use    | 1-5 (low)         | Low to Medium  | Low          | Structured, schema-validated tool dispatch  |
| ReAct       | 3-10+ (dynamic)   | Medium, high var| Variable    | Open-ended multi-step tool use              |
| Routing     | 2 (fixed)         | Low            | Low          | Input classification + handler dispatch     |
