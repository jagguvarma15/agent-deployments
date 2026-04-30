# Pattern: Parallel Calls (Fan-out / Fan-in)

**One-liner:** Run multiple independent LLM calls or tool invocations concurrently, then aggregate their results.

## When to use

- You have N independent sub-tasks that don't depend on each other (e.g., enrich N records, summarize N documents).
- Latency matters — sequential execution of N tasks takes N× as long.
- Each sub-task uses the same prompt/tool with different inputs (batch processing pattern).
- You need to aggregate or merge results after all sub-tasks complete.

## When NOT to use

- Sub-tasks depend on each other's outputs (use Prompt Chaining).
- N is very large (100+) and you'd hit rate limits. Add concurrency controls.
- The sub-tasks need to coordinate or share state mid-execution (use Multi-Agent).

## Core flow

```
Input (list of items)
    |
    v
  [Fan-out] ──> spawn N concurrent tasks
    |
    ├──> [Task 1: process item A] ──┐
    ├──> [Task 2: process item B] ──┤
    ├──> [Task 3: process item C] ──┤
    └──> [Task N: process item N] ──┘
                                    |
                                    v
                              [Fan-in / Aggregate]
                                    |
                                    v
                              Combined result
```

### Variants

- **Homogeneous fan-out:** All tasks use the same prompt/tool, different inputs. Classic batch processing.
- **Heterogeneous fan-out:** Different tasks run different prompts/tools in parallel (e.g., summarize + extract entities + classify sentiment simultaneously on the same document).
- **Fan-out with partial failure:** Some tasks may fail. Collect successes, report failures, optionally retry.
- **Chunked fan-out:** For large N, split into batches with concurrency limits (e.g., 10 at a time).

## Key components

- **Splitter:** Divides the input into independent work units.
- **Worker:** The LLM call or tool invocation applied to each unit. Should be stateless and idempotent.
- **Concurrency controller:** Limits how many workers run simultaneously. Prevents rate-limit exhaustion. In Python: `asyncio.Semaphore`. In TS: `Promise.all()` with chunking.
- **Aggregator:** Merges individual results into a combined output. May be a simple list, a summary, or a structured merge.
- **Error handler:** Decides what to do when individual tasks fail (skip, retry, abort all).

## Common pitfalls

- **No concurrency limit:** Firing 100 parallel LLM calls will hit rate limits. Use a semaphore or batch size.
- **One failure kills all:** If using `Promise.all()` or `asyncio.gather()` without error handling, one failure cancels everything. Use `Promise.allSettled()` / `return_exceptions=True`.
- **Results out of order:** Parallel results may return in any order. Preserve input-output mapping (index or ID).
- **Context window limits:** If the aggregator tries to merge too many results into one prompt, it may exceed the context window. Summarize incrementally.
- **Cost multiplication:** N parallel calls = N× the cost of one call. Make sure parallelism is worth it vs. a single batched prompt.

## Framework fit

| Framework | Native support | Notes |
|-----------|----------------|-------|
| Pydantic AI | `asyncio.gather()` with multiple `agent.run()` calls | Natural — async-first, clean ergonomics |
| Mastra | `Promise.all()` with agent calls, or workflow parallel steps | TS-native async |
| LangGraph | `Send()` API for map-reduce fan-out | Works but heavier than raw async |
| Vercel AI SDK | `Promise.all()` with `generateText()` calls | Simple and effective |
| CrewAI | Parallel task execution in a crew | Built-in but less control over concurrency |

## Reference implementations

- [recipes/parallel-enricher.md](../recipes/parallel-enricher.md) — Parallel batch enrichment with Pydantic AI / Mastra (skeleton)
