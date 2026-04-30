# Pattern: Prompt Chaining

**One-liner:** Break a complex task into a fixed sequence of LLM calls where each step's output feeds the next step's input.

## When to use

- The task naturally decomposes into ordered stages (e.g., research → outline → draft → edit).
- Each stage has a clear input/output contract.
- You want deterministic flow — every request follows the same pipeline.
- Quality benefits from specialized prompts per stage rather than one monolithic prompt.

## When NOT to use

- The sequence of steps isn't known upfront (use ReAct).
- Steps need to run in parallel, not sequentially (use Parallel Calls).
- The agent needs to decide whether to skip or repeat steps (use Plan-and-Execute).

## Core flow

```
Input
  |
  v
[Stage 1: Research] ──> research notes
  |
  v
[Stage 2: Outline] ──> structured outline
  |
  v
[Stage 3: Draft] ──> full draft
  |
  v
[Stage 4: Edit] ──> polished output
  |
  v
Final output
```

### Variants

- **Linear chain:** A → B → C → D. Simplest form.
- **Chain with validation gates:** After each stage, validate the output (schema check, quality check). Retry or fail early if validation fails.
- **Chain with accumulation:** Each stage receives not just the previous output, but all prior outputs (snowball context).
- **Chain with human-in-the-loop:** Pause between stages for human review/approval before continuing.

## Key components

- **Stage:** A single LLM call with a focused system prompt. Each stage is a pure function: input → output.
- **Schema:** Structured output types (Pydantic models / Zod schemas) that define the contract between stages. Type safety prevents silent failures.
- **Pipeline orchestrator:** Runs stages in order, passing outputs forward. Can be as simple as sequential `await` calls.
- **Validation gate (optional):** Checks stage output before passing it to the next stage. Can retry, modify, or abort.

## Common pitfalls

- **Context bloat:** If you pass all prior stage outputs to every stage, context grows linearly. Only pass what each stage needs.
- **Error propagation:** A bad output from stage 1 cascades through all subsequent stages. Add validation gates at critical points.
- **Prompt coupling:** If stage 2's prompt assumes a specific format from stage 1, changing stage 1 breaks stage 2. Use explicit schemas.
- **Unnecessary chaining:** If one good prompt can do the job, don't split it into 3 stages. More stages = more latency + cost.
- **No partial results:** If the pipeline fails at stage 3, you lose stages 1-2 unless you persist intermediate outputs.

## Framework fit

| Framework | Native support | Notes |
|-----------|----------------|-------|
| Pydantic AI | Sequential `agent.run()` calls with typed `result_type` per stage | Natural fit — type safety between stages |
| Vercel AI SDK | `generateObject()` per stage, pipe outputs manually | Clean TS implementation |
| LangGraph | Linear graph with one node per stage | Works but overkill for simple chains |
| Mastra | Sequential agent calls or workflow steps | Mastra workflows support chaining natively |
| CrewAI | Sequential task execution in a crew | Works but heavy for a simple pipeline |

## Reference implementations

- [recipes/content-pipeline.md](../recipes/content-pipeline.md) — Multi-stage content generation pipeline (Pydantic AI / Vercel AI SDK, skeleton)
