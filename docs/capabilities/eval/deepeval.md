---
id: eval.deepeval
kind: eval
provides: [eval_runner, rag_metrics]
env_vars: [ANTHROPIC_API_KEY, OPENAI_API_KEY]
docker: null
probe: null
bootstrap_step: bootstrap_evals
emit_files: []
docs: |
  DeepEval for RAG-specific metrics — faithfulness, answer relevancy, contextual
  precision/recall. Python-native test suite that runs the eval as `pytest` cases.
---

# Capability: eval.deepeval

> Deep reference: [`stack/eval-deepeval-ragas-promptfoo.md`](../../stack/eval-deepeval-ragas-promptfoo.md). This page is the provisioning contract.

**Used for:** RAG eval with first-class retrieval metrics (faithfulness, answer relevancy, contextual precision/recall) and a `pytest`-shaped runner.

## Why pick this

When promptfoo's prompt-grid eval shape is the wrong granularity — RAG evaluation needs per-retrieved-document scoring, not just per-prompt assertions. DeepEval's metrics treat retrieval as a first-class signal: faithfulness scores whether the answer is grounded in the retrieved context, answer relevancy scores whether the answer addresses the question, contextual precision/recall score whether the retriever pulled the right documents.

If you're not running RAG, prefer [`eval.promptfoo`](promptfoo.md) — it's lighter-weight and faster to iterate on.

## Local setup

DeepEval is a Python library; no service to run. Add to the generated project's `pyproject.toml`:

```toml
[dependency-groups]
dev = ["deepeval>=2.0.0"]
```

Or to `package.json` for TypeScript projects that delegate eval to a Python sidecar:

```json
{
  "scripts": {
    "eval": "uv run --with deepeval pytest tests/eval/"
  }
}
```

## Bootstrap (post docker_up)

`bootstrap_evals` (shared with `eval.promptfoo` and `eval.ragas`) writes the initial baseline. For DeepEval specifically, the baseline is the pass-rate across declared RAG cases under `tests/eval/`. Stored in `manifest.answers["eval_baseline"]` so subsequent runs can compare against it.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `ANTHROPIC_API_KEY` | — | The model under test |
| `OPENAI_API_KEY` | — | Required for the DeepEval metric scorers (GPT-4 powers faithfulness / contextual relevancy / etc.) |

## Cloud / production

DeepEval is a dev/CI tool — no production runtime. In CI, run the eval suite as part of test gates; fail the build if the pass-rate drops below the stored baseline.

For richer dashboards, push results to [Confident AI](https://confident-ai.com/) (DeepEval's hosted analytics layer) or self-host the open-source reporter.

## When to swap it

- **→ [`eval.promptfoo`](promptfoo.md)** for non-RAG agents or prompt-grid evaluation.
- **→ [`eval.ragas`](ragas.md)** for academic-style benchmarking against a labeled reference dataset.

## See also

- `stack/eval-deepeval-ragas-promptfoo.md` — depth on the three-eval compound pick.
- `cross-cutting/testing-strategy.md` — three-tier test strategy.
