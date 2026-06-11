---
id: eval.deepeval
kind: eval
layer: eval
provides: [eval_runner, rag_metrics]
env_vars: [ANTHROPIC_API_KEY, OPENAI_API_KEY]
docker: null
probe: null
bootstrap_step: bootstrap_evals
provisioning_time: instant
cost_tier: per-call
est_tokens: 600
card:
  name: DeepEval
  description: "Python-native LLM/RAG eval framework with pytest integration and built-in RAG metrics."
  capabilities_provided: [rag_eval, pytest_runner, llm_judge_scoring]
  required_credentials: [ANTHROPIC_API_KEY, OPENAI_API_KEY]
emit_files: []
docs: |
  DeepEval for RAG-specific metrics (faithfulness, answer relevancy, contextual
  precision/recall). Python-native test suite that runs as `pytest` cases.
---

# Capability: eval.deepeval

> Deep reference: [`stack/eval-deepeval-ragas-promptfoo.md`](../../stack/eval-deepeval-ragas-promptfoo.md). This page is the provisioning contract.

**Used for:** RAG eval with first-class retrieval metrics (faithfulness, answer relevancy, contextual precision/recall) in a `pytest` runner.

## Local setup

DeepEval is a Python library; no service. Add to the generated project's `pyproject.toml`:

```toml
[dependency-groups]
dev = ["deepeval>=2.0.0"]
```

For TypeScript projects, run via a Python sidecar:

```json
{
  "scripts": {
    "eval": "uv run --with deepeval pytest tests/eval/"
  }
}
```

## Bootstrap (post docker_up)

`bootstrap_evals` (shared with `eval.promptfoo` and `eval.ragas`) records the initial pass-rate as the baseline in `manifest.answers["eval_baseline"]`. Subsequent runs compare against it.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `ANTHROPIC_API_KEY` | — | The model under test |
| `OPENAI_API_KEY` | — | Required for DeepEval's metric scorers (GPT-4 powers faithfulness / contextual relevancy) |

## Client integration

**Python (pytest case):**

```python
from deepeval import assert_test
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase

def test_research_answers_grounded():
    case = LLMTestCase(
        input="What's the capital of France?",
        actual_output=run_agent("What's the capital of France?"),
        retrieval_context=["Paris is the capital of France."],
    )
    assert_test(case, [
        FaithfulnessMetric(threshold=0.8),
        AnswerRelevancyMetric(threshold=0.7),
    ])
```

## Cloud / production

Dev/CI tool — no production runtime. For richer dashboards, push results to [Confident AI](https://confident-ai.com/) or self-host the OSS reporter.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `OpenAI API key required` | `OPENAI_API_KEY` not set | DeepEval's metric scorers use OpenAI by default; export the key or override the scorer model |
| Tests pass locally, fail in CI | Different model versions between envs | Pin `model="claude-sonnet-4-6"` in the LLM call; pin GPT-4 scorer version |
| Metric returns 0.0 unexpectedly | `retrieval_context` not populated for RAG metrics | Faithfulness + contextual metrics require `retrieval_context`; pass the retrieved chunks explicitly |
| Slow eval suite | Too many cases scored sequentially | Use `pytest-xdist` for parallel runs: `uv run pytest -n 4 tests/eval/` |

## See also

- [`stack/eval-deepeval-ragas-promptfoo.md`](../../stack/eval-deepeval-ragas-promptfoo.md) — depth on the three-eval compound pick
- [`cross-cutting/testing-strategy.md`](../../cross-cutting/testing-strategy.md) — three-tier test strategy
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
