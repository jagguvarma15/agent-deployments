---
id: eval.ragas
kind: eval
layer: eval
provides: [eval_runner, rag_metrics, benchmark]
env_vars: [ANTHROPIC_API_KEY, OPENAI_API_KEY]
docker: null
probe: null
bootstrap_step: bootstrap_evals
provisioning_time: instant
cost_tier: per-call
est_tokens: 600
card:
  name: RAGAS
  description: "Academic-style RAG benchmarking against a labeled dataset with answer/context metrics."
  capabilities_provided: [rag_eval, batch_benchmark, dataset_aggregation]
  required_credentials: [ANTHROPIC_API_KEY, OPENAI_API_KEY]
emit_files: []
docs: |
  RAGAS for academic-style RAG benchmarking — reference-answer comparison,
  per-question scoring, dataset-aware aggregation. Best for batch evaluation
  against a labeled test set.
tags: [eval, rag-eval, python]
when_to_load: "recipe declares eval.ragas"
---

# Capability: eval.ragas

> Deep reference: [`stack/eval-deepeval-ragas-promptfoo.md`](../../stack/eval-deepeval-ragas-promptfoo.md). This page is the provisioning contract.

**Used for:** RAG evaluation against a labeled dataset with academic metrics (answer correctness, semantic similarity, context precision/recall, faithfulness).

## Local setup

Python library; no service. Add to the generated project's `pyproject.toml`:

```toml
[dependency-groups]
dev = ["ragas>=0.2.0", "datasets>=2.0.0"]
```

The labeled dataset typically lives at `tests/eval/dataset.jsonl` with one JSON object per line: `{"question": "...", "ground_truth": "...", "contexts": [...]}`.

## Bootstrap (post docker_up)

`bootstrap_evals` runs the initial benchmark and stores per-metric averages in `manifest.answers["eval_baseline"]`. CI compares subsequent runs against the baselines.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `ANTHROPIC_API_KEY` | — | The model under test |
| `OPENAI_API_KEY` | — | Required for RAGAS's reference-comparison metrics |

## Client integration

**Python (batch benchmark):**

```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from datasets import Dataset

# Load labeled dataset
rows = [json.loads(line) for line in open("tests/eval/dataset.jsonl")]
ds = Dataset.from_dict({
    "question":     [r["question"] for r in rows],
    "answer":       [run_agent(r["question"]) for r in rows],
    "contexts":     [r["contexts"] for r in rows],
    "ground_truth": [r["ground_truth"] for r in rows],
})

result = evaluate(ds, metrics=[
    faithfulness, answer_relevancy, context_precision, context_recall,
])
print(result.to_pandas().describe())
```

## Cloud / production

Dev/CI tool — no production deployment. Reports written as JSON; CI gates on per-metric thresholds set in the eval config.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Missing field 'contexts'` | Dataset row lacks the contexts list | Every row needs `question`, `answer`, `contexts[]`, `ground_truth` — re-emit dataset |
| Eval takes hours | Sequential scorer calls | Set `evaluate(..., raise_exceptions=False, max_workers=8)` for parallelism |
| `answer_correctness` consistently low | Reference answers too specific | RAGAS uses semantic similarity; broader ground-truth phrasing improves scores |
| Out-of-memory on large datasets | All rows loaded in memory | Stream via `Dataset.from_generator` or batch into chunks of 100 |

## See also

- [`stack/eval-deepeval-ragas-promptfoo.md`](../../stack/eval-deepeval-ragas-promptfoo.md) — depth on the three-eval pick
- [`cross-cutting/testing-strategy.md`](../../cross-cutting/testing-strategy.md) — three-tier test strategy
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
