---
id: eval.ragas
kind: eval
provides: [eval_runner, rag_metrics, benchmark]
env_vars: [ANTHROPIC_API_KEY, OPENAI_API_KEY]
docker: null
probe: null
bootstrap_step: bootstrap_evals
emit_files: []
docs: |
  RAGAS for academic-style RAG benchmarking — reference-answer comparison,
  per-question scoring, dataset-aware aggregation. Best for batch evaluation
  against a labeled test set.
---

# Capability: eval.ragas

> Deep reference: [`stack/eval-deepeval-ragas-promptfoo.md`](../../stack/eval-deepeval-ragas-promptfoo.md). This page is the provisioning contract.

**Used for:** RAG evaluation against a labeled dataset with academic metrics (answer correctness, semantic similarity, context precision/recall, faithfulness).

## Why pick this

RAGAS is the right fit when you have a *labeled* dataset (question + reference answer) and want metrics aligned with academic RAG benchmarks. It runs as a batch job, scores every `(question, retrieved-context, generated-answer)` tuple, and aggregates per-dataset. [`eval.deepeval`](deepeval.md) is closer to a unit-test shape; RAGAS is closer to a benchmark shape.

Pick this when reporting eval results externally, comparing against published benchmarks, or when your test set has hundreds of cases (RAGAS amortizes overhead better than per-case runners).

## Local setup

Python library; no service. Add to the generated project's `pyproject.toml`:

```toml
[dependency-groups]
dev = ["ragas>=0.2.0", "datasets>=2.0.0"]
```

The labeled dataset typically lives at `tests/eval/dataset.jsonl` with one JSON object per line: `{"question": "...", "ground_truth": "...", "contexts": [...]}`.

## Bootstrap (post docker_up)

`bootstrap_evals` (shared with `eval.promptfoo` and `eval.deepeval`) runs the initial benchmark on the labeled dataset and stores the per-metric averages in `manifest.answers["eval_baseline"]`. CI compares subsequent runs against these baselines.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `ANTHROPIC_API_KEY` | — | The model under test |
| `OPENAI_API_KEY` | — | Required for RAGAS's reference-comparison metrics (semantic similarity, answer correctness) |

## Cloud / production

Dev/CI tool. No production deployment. Reports are written as JSON; CI gates on per-metric thresholds set in the eval config (typical: `answer_correctness >= baseline - 0.05`, `faithfulness >= 0.9`).

## When to swap it

- **→ [`eval.promptfoo`](promptfoo.md)** for non-RAG or grid-shaped evaluation.
- **→ [`eval.deepeval`](deepeval.md)** for `pytest`-shaped per-case evaluation without a labeled dataset.

## See also

- `stack/eval-deepeval-ragas-promptfoo.md` — depth on the three-eval compound pick.
- `cross-cutting/testing-strategy.md` — three-tier test strategy.
