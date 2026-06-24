# Prompt Engineering

The prompt is the instruction text an LLM acts on — the role framing, the task, the input data, and the shape of the expected answer. Prompt engineering is the craft of writing that text so the model does the right thing reliably. It is the foundation every pattern in this repository builds on: a ReAct loop, a RAG pipeline, and an evaluator-optimizer are all *sequences of prompts* with control flow around them.

This page is the cross-cutting vocabulary. It does not hold the concrete prompt text for any pattern — those live in each pattern's `prompts/` directory as typed files (see [Where the templates live](#where-the-templates-live)). Read this first; read the per-pattern prompts when you implement.

## Prompt engineering vs context engineering

These are different disciplines that share one scarce resource — the context window.

- **Prompt engineering** is about *wording and structure*: how a single instruction is phrased so the model interprets it correctly. (this page)
- **[Context engineering](./context-engineering.md)** is about *what tokens enter the window, in what shape, and on whose authority* across every turn — the four levers of select / compress / prune / persist.

A useful split: prompt engineering decides what one call *says*; context engineering decides what that call *can see*. A perfectly worded prompt fails if the relevant context was pruned two turns ago; a well-managed window underperforms if the instruction is vague. You need both.

## The anatomy of a prompt

Most production prompts have the same parts, in roughly this order:

- **Role / system framing** — who the model is acting as and the standing constraints ("You are a triage classifier. You only output one of the labels below.").
- **Task instruction** — the single thing to do, stated imperatively and specifically.
- **Input data** — the material to act on, clearly delimited from the instructions (see [Prompts and untrusted input](#prompts-and-untrusted-input)).
- **Examples** — zero or more demonstrations of input → output (few-shot).
- **Output contract** — the exact shape of the answer (a schema, a label set, a format).

Not every prompt needs every part, but naming them makes a prompt reviewable: you can ask "is the task unambiguous?", "are the examples representative?", and "is the output contract enforceable?" independently.

## Core techniques

- **Be specific and imperative.** "Summarize the ticket in two sentences for an on-call engineer" beats "summarize this". Specificity is the cheapest quality lever there is.
- **Spend few-shot tokens deliberately.** Examples are the strongest way to pin format and edge-case handling — and the easiest way to bloat a prompt. Add them when zero-shot is unreliable; prefer a few diverse, correct examples over many similar ones.
- **Scaffold reasoning when it helps.** Asking for step-by-step reasoning before the answer improves multi-step tasks. Reasoning-tuned models often do this internally — don't pay for redundant "think step by step" boilerplate when the model already reasons.
- **Separate instructions from data with delimiters.** Wrap untrusted or free-form input in explicit markers so the model knows where instructions end and data begins.
- **Prefer positive instructions.** "Respond only in English" is followed more reliably than "don't use other languages." State what to do, not only what to avoid.
- **One prompt, one job.** When a prompt grows conditionals ("if X do this, else that, but also…"), that is the signal to split it — into [Prompt Chaining](../patterns/prompt-chaining/overview.md) or [Routing](../patterns/routing/overview.md), where each call has a single responsibility.

## Controlling the output format

For anything downstream code consumes — tool calls, pipeline steps, structured extraction — the output contract is the highest-leverage part of the prompt. In order of preference:

1. **Constrained decoding / structured outputs.** When the provider supports a strict schema or tool/function definition, use it: the model is forced to emit valid JSON matching your schema, which is far more reliable than parsing prose.
2. **Tool schemas.** For tool use, the [Tool Use](../primitives/tool_use/overview.md) primitive's function schema *is* the output contract; keep parameter names and descriptions tight.
3. **Ask, validate, retry.** When neither is available, specify the format precisely, validate the response against a schema, and retry on mismatch. Treat "the model usually returns JSON" as a bug waiting to happen.

The principle: make the desired output the *only* output the model can easily produce, rather than hoping it complies.

## Prompts and untrusted input

The moment a prompt interpolates content a user or a tool produced, prompt engineering meets the [security](./security-and-safety.md) boundary. Text in the data slot can try to read as instructions — that is prompt injection. Two rules:

- **Delimit and label untrusted input** (wrap it in a clear block) and instruct the model to treat everything inside as data, never as commands.
- **Never give one prompt both untrusted input and a dangerous capability.** That separation is an architecture decision — see the [Guardrails](../modifiers/guardrails/overview.md) modifier's dual-LLM split — not something prompt wording alone can guarantee.

## Where the templates live

This page is vocabulary, not a prompt library. Every LLM call inside a pattern has a canonical prompt file at `patterns/<name>/prompts/<role>.md`, with a typed frontmatter contract (`role`, `inputs`, `output_schema`, `model_hint`) so tooling can reason about it without parsing the prose body. That contract is defined in the [Style Guide → Typed prompts](../meta/style-guide.md). When you implement a pattern, write its prompts there; the techniques on this page are what those files specialize.

## Iterating on prompts

Treat prompts as code, not as throwaway strings:

- **Version them.** A prompt change is a behavior change — diff it, review it, roll it out deliberately.
- **Test them with evals.** A prompt edit that fixes one case often regresses another; gate changes with a golden set. See [Evals & Quality](./evals-and-quality.md).
- **Pin the model.** Prompts are model-specific; wording tuned for one model (or one version) can degrade on another. The `model_hint` in the prompt frontmatter records the intended tier.

## Related

- [Context Engineering](./context-engineering.md) — what enters the window, across the loop
- [Terminology](./terminology.md) — precise definitions of prompt, tool, and context window
- [Tool Use](../primitives/tool_use/overview.md) — function schemas as output contracts
- [Security & Safety](./security-and-safety.md) — prompt injection and the trust boundary
- [Evals & Quality](./evals-and-quality.md) — how to test a prompt change
- [Style Guide → Typed prompts](../meta/style-guide.md) — the per-pattern prompt file contract
