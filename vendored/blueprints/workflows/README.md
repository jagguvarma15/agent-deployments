# Workflows (retired location)

> **This directory was folded into [`../patterns/`](../patterns/) in the taxonomy refactor.** Workflows are flow shapes too — just code-controlled rather than LLM-controlled. They now live alongside agent patterns with `category: workflow` set in each `metadata.json`.

## Where each workflow lives now

| Workflow | New location |
|---|---|
| Prompt Chaining | [`../patterns/prompt-chaining/`](../patterns/prompt-chaining/) |
| Parallel Calls | [`../patterns/parallel-calls/`](../patterns/parallel-calls/) |
| Orchestrator-Worker | [`../patterns/orchestrator-worker/`](../patterns/orchestrator-worker/) |
| Evaluator-Optimizer | [`../patterns/evaluator-optimizer/`](../patterns/evaluator-optimizer/) |

## Why the merge

Workflows and agent patterns are the same *kind* of thing: a control-flow shape that produces an outcome. The historical split (workflows for code-controlled flow, patterns for LLM-controlled flow) was a useful pedagogical distinction but a confusing taxonomy boundary. After the v2 catalog reshape, the distinction lives on as a single `category` field on each pattern's metadata (`workflow` vs `agent`) rather than as separate top-level directories.

For consumers that still walk `workflows[]` from the catalog: the top-level `workflows[]` key is preserved as a derived view of `patterns[]` filtered by `category: workflow`. That backward-compat affordance will be removed in a future release once consumers migrate.

See [`../README.md`](../README.md) for the three-tier taxonomy (patterns / primitives / modifiers) and [`../foundations/choosing-a-pattern.md`](../foundations/choosing-a-pattern.md) for the picker decision tree.
