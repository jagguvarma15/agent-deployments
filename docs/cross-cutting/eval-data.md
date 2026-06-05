# Cross-cutting: Eval Data — generation and golden-set curation

**Concern:** How to grow, curate, version, and monitor the JSONL datasets that recipes ship as `eval/dataset.jsonl`.
**Lives in:** `eval/datasets/<name>.jsonl` inside each generated project, plus the patterns here.
**Related:** [`testing-strategy.md`](testing-strategy.md), [`../capabilities/eval/promptfoo.md`](../capabilities/eval/promptfoo.md), [`../capabilities/eval/deepeval.md`](../capabilities/eval/deepeval.md), [`../stack/vector-qdrant.md`](../stack/vector-qdrant.md), [`cost-tracking.md`](cost-tracking.md).

Recipes ship a 10-row inline example so the project boots with `make eval` passing. This document is for the next step: turning that seed into a real evaluation harness.

## 1. What an eval dataset is for

| Purpose | In scope | Out of scope |
|---------|----------|--------------|
| Regression detection across recipe / prompt / model changes | yes | |
| Pinning behavior on edge cases that already shipped a bug | yes | |
| Validating a framework swap (Pydantic-AI -> LangChain) preserves behavior | yes | |
| Comparing two models on the same task | yes | |
| Training data for fine-tuning | | no |
| Production traffic replay (use observability traces, not goldens) | | no |
| Demos / fixtures for unit tests (use `tests/unit/fixtures/`) | | no |

A golden set is small, curated, and slow-changing. It is not a benchmark and not a corpus.

## 2. Anatomy of a row

Every recipe uses JSONL. One row per line, one test case per row. The minimum shape:

```json
{"input": "...", "expected": "...", "metadata": {}}
```

Recipes extend `expected` with task-specific assertions. Three real rows from [`../recipes/research-assistant.md`](../recipes/research-assistant.md):

```json
{"id": "research-001", "category": "tool-sequencing", "question": "What are the main differences between supervised and unsupervised learning?", "min_steps": 2, "max_steps": 5, "expected_tool_calls": ["search"], "expected_answer_contains": ["supervised", "unsupervised", "label"]}
{"id": "research-002", "category": "multi-source-synthesis", "question": "Compare RAG and fine-tuning as LLM customization strategies.", "min_steps": 2, "max_steps": 5, "expected_tool_calls": ["search"], "expected_answer_contains": ["RAG", "fine-tuning"], "expected_min_sources": 2}
{"id": "research-003", "category": "clarification", "question": "How does the system work?", "expected_clarification": true, "expected_tool_calls": []}
```

Conventions:

- **`id`** — stable across runs. Include a recipe slug prefix (`research-001`) so multi-recipe eval runs don't collide.
- **`category`** — one of the strata you used to sample (see §4). Lets you compute pass rate per stratum.
- **`expected_*`** — assertions that the evaluator checks. Avoid stuffing a free-text "expected_answer" string when the real assertion is "must contain these substrings" or "must call this tool".
- **`metadata`** — provenance: `{"source": "synthetic", "generator": "haiku-v2", "reviewed_by": "alice", "frozen_at": "2026-05-12"}`. Lets you re-run synthesis for a stratum without losing the manual review pass on the rest.

Schema drift is the most common failure mode — pin the assertion keys in your recipe's `## Eval Dataset` section and resist adding ad-hoc ones case by case.

## 3. Synthetic generation via Haiku

Use Haiku to generate candidate rows from a topic distribution, then human-curate. Pure-Haiku data without review is noisy; Haiku-then-human is fast and good.

```python
"""Seed N candidate eval rows from a topic distribution, dedupe by embedding similarity.

Usage:
    uv run --with anthropic --with numpy python gen_eval.py \
        --topics topics.txt --n 50 --out candidates.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path

import numpy as np
from anthropic import Anthropic

MODEL = "claude-haiku-4-5-20251001"
SYSTEM = (
    "You generate evaluation test cases for a research assistant. "
    "Each case is one JSON object on one line with keys: id, category, question, "
    "expected_tool_calls (list of tool names), expected_answer_contains (list of substrings). "
    "Questions must be specific enough that a correct answer is verifiable. "
    "Vary phrasing, length, and difficulty. No prose outside the JSON."
)

CATEGORIES = ["tool-sequencing", "multi-source-synthesis", "clarification", "adversarial"]


def generate(client: Anthropic, topic: str, category: str, idx: int) -> dict:
    msg = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM,
        messages=[{
            "role": "user",
            "content": f"Topic: {topic}\nCategory: {category}\nid: synth-{idx:04d}\nEmit one JSON object.",
        }],
    )
    text = msg.content[0].text.strip()
    return json.loads(text)


def embed(client: Anthropic, text: str) -> np.ndarray:
    # Replace with your embedding provider; this is a placeholder hash-vector
    # so the dedup logic is self-contained. See ../stack/vector-qdrant.md.
    rng = np.random.default_rng(abs(hash(text)) % (2**32))
    return rng.standard_normal(384)


def dedupe(rows: list[dict], threshold: float = 0.92) -> list[dict]:
    client = Anthropic()
    kept: list[tuple[dict, np.ndarray]] = []
    for row in rows:
        v = embed(client, row["question"])
        if all(float(np.dot(v, u) / (np.linalg.norm(v) * np.linalg.norm(u))) < threshold for _, u in kept):
            kept.append((row, v))
    return [r for r, _ in kept]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topics", type=Path, required=True)
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    assert os.environ.get("ANTHROPIC_API_KEY"), "ANTHROPIC_API_KEY required"
    topics = [t.strip() for t in args.topics.read_text().splitlines() if t.strip()]
    client = Anthropic()

    rows: list[dict] = []
    for i in range(args.n):
        topic = random.choice(topics)
        category = random.choice(CATEGORIES)
        try:
            rows.append(generate(client, topic, category, i))
        except (json.JSONDecodeError, IndexError):
            continue  # discard malformed candidates

    deduped = dedupe(rows)
    args.out.write_text("\n".join(json.dumps(r) for r in deduped) + "\n")
    print(f"kept {len(deduped)}/{len(rows)} after dedupe -> {args.out}")


if __name__ == "__main__":
    main()
```

Notes:

- The `embed()` placeholder keeps the script self-contained. In a real run, swap it for Voyage / Cohere / your hosted embeddings and write vectors to Qdrant — see [`../stack/vector-qdrant.md`](../stack/vector-qdrant.md) for the standard collection layout.
- Haiku occasionally emits trailing prose or a code fence around the JSON. The `try/except json.JSONDecodeError` is the cheap fix; for higher yield, use `response_format`-style schema enforcement once your SDK exposes it.
- Generate 3–5× the rows you want to keep — dedupe + manual review trims aggressively.

## 4. Golden-set curation

Synthesis produces *candidates*. The golden set is what survives review.

**Sampling strategy** — stratify before you sample:

| Stratum | Why include | Share of set |
|---------|-------------|--------------|
| Happy path | What 80% of real traffic looks like | ~40% |
| Edge cases | Empty input, very long input, multilingual, malformed | ~25% |
| Adversarial | Prompt injection, jailbreaks, PII bait | ~15% |
| Known regressions | Every bug that ever shipped, frozen as a case | ~20% |

**Manual review pass** — for each candidate:

1. Is the question well-formed and unambiguous?
2. Are the assertions correct? (run the agent once, accept the output as the new expected if it's right)
3. Does the row add coverage, or does it duplicate something already in the set?

**Freeze + version** — commit the JSONL. Tag with `eval-v1`, `eval-v2`. Every release that changes the agent's behavior in a way you accept either passes the existing set or introduces `eval-v(N+1)` with the new expected values. **Do not** edit a frozen case in place — that erases the regression history.

## 5. Drift detection

Run the current agent against the golden set on a schedule. Alert when pass rate drops.

```yaml
# .github/workflows/eval-drift.yml
on:
  schedule: [{cron: "0 14 * * 1"}]   # Mondays 14:00 UTC
  workflow_dispatch:
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv run pytest tests/eval --jsonl-report=report.json
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      - run: python scripts/alert_on_regression.py report.json --threshold 0.90
```

A 5-point drop week-over-week is almost always a real regression (prompt change, model rotation, dependency bump). Wire the alert to the channel oncall watches. For runner integration with Promptfoo, see [`../capabilities/eval/promptfoo.md`](../capabilities/eval/promptfoo.md); for DeepEval metric harnesses, see [`../capabilities/eval/deepeval.md`](../capabilities/eval/deepeval.md).

## 6. Evaluator strategies

Pick the cheapest evaluator that gives you a signal you trust.

| Strategy | Use when | Cost | Failure mode |
|----------|----------|------|--------------|
| Exact match / regex / substring | Closed-class outputs: tool name, intent label, structured field | ~free | Misses semantically-correct rephrasings |
| Numeric tolerance | Outputs are numbers (counts, scores, ranks) | ~free | Hides large rank swaps within tolerance |
| Embedding similarity | Open-class short answers; "the model said roughly the right thing" | embed cost only | Calibration drifts when embedding model changes |
| LLM-as-judge | Subjective: faithfulness, groundedness, tone, helpfulness | judge tokens per row | Judge bias toward verbose answers; expensive at scale |
| Programmatic rubric | Multi-criterion: "answer cites ≥2 sources AND ≤500 tokens AND uses no banned phrases" | combination | Brittle if you keep adding criteria mid-stream |

Default to the lightest evaluator. Reach for LLM-as-judge only when the task is irreducibly subjective.

## 7. LLM-as-judge prompt template

Use a **stronger** model than the production model as the judge. Run the judge with `temperature=0`. Always include the rubric inline — judges that improvise rubrics are inconsistent.

```text
You are evaluating an answer for groundedness.

Question:
{question}

Sources retrieved by the agent:
{sources}

Agent answer:
{answer}

Rubric (score each independently, 0 or 1):
  G1. Every factual claim in the answer is supported by at least one source.
  G2. The answer does not contradict any source.
  G3. The answer cites sources inline (by index or title) for non-trivial claims.
  G4. The answer says "I don't know" when sources are insufficient (instead of guessing).

Output JSON only:
{"G1": 0|1, "G2": 0|1, "G3": 0|1, "G4": 0|1, "notes": "<1 sentence explaining any 0>"}
```

Aggregate per-rubric pass rates separately; a 90% mean score can hide a 40% groundedness collapse. For broader grounding patterns (retrieval coverage, citation density, hallucination triage) cross-reference your project's grounding doc — if your recipe doesn't yet ship one, treat this as a TODO.

## 8. Storage and ops

```
eval/
├── datasets/
│   ├── golden.jsonl              # frozen, version-tagged
│   ├── golden.v1.jsonl           # historical snapshot kept for diffing
│   └── candidates.jsonl          # synthetic output, not committed
├── reports/                       # per-run reports, gitignored
│   └── 2026-05-12.json
├── gen_eval.py                   # synthesis script (§3)
└── judge_prompts/
    └── groundedness.md           # rubric (§7), version-controlled
```

- **Commit** golden datasets. **Don't commit** candidates or reports.
- **Bump the dataset filename**, don't edit in place. `golden.v2.jsonl` makes regressions diffable.
- **Datasets travel with the recipe**, not with the framework — swapping Pydantic-AI for LangChain reuses the same golden set.

Consumers:

- Promptfoo reads `eval/datasets/golden.jsonl` via `tests:` in `promptfooconfig.yaml`. See [`../capabilities/eval/promptfoo.md`](../capabilities/eval/promptfoo.md).
- DeepEval reads it via `EvaluationDataset.from_jsonl()`. See [`../capabilities/eval/deepeval.md`](../capabilities/eval/deepeval.md).
- Custom pytest harness: glob the dataset, parametrize one test per row, emit a JSON report for `alert_on_regression.py` to consume.

## 9. Cost guardrails

Eval runs can outspend production if uncapped. The numbers below are starting points — tune to your traffic.

| Lever | Default |
|-------|---------|
| Per-run row cap (full set) | 200 |
| Per-run row cap (PR smoke) | 20, sampled stratified |
| Daily eval spend cap | $5 dev / $50 prod-mirror |
| Judge model | One tier above production (`claude-sonnet-4-6` judging Haiku output) |
| Cache | Enable prompt caching on the judge system prompt — see [`cost-tracking.md`](cost-tracking.md) |
| Observability | Emit `eval_run_completed` with `rows`, `pass_rate`, `cost_usd` per stratum |

When the dataset grows past ~500 rows, switch the per-PR run to a stratified sample and reserve the full run for `main` + nightly.

## 10. Anti-patterns

- **LLM-as-judge for closed-class tasks.** If the assertion is "tool `search` was called", use exact match. Spending judge tokens to check a substring is wasteful and noisy.
- **Judging with the production model.** A model that can't solve the task usually can't grade it either. Use one tier up.
- **Regenerating the golden set when the agent regresses.** Fix the agent, not the goldens. Regenerating is how you lose every regression you ever caught.
- **One giant prompt-template column in JSONL.** If the rendered prompt depends on retrieval, store the *inputs* (`question`, `user_id`), not the rendered prompt. Lets you re-eval after a prompt edit without rebuilding the dataset.
- **Mixing eval data with unit-test fixtures.** Fixtures pin code behavior and live next to the test. Golden cases pin agent behavior and live in `eval/datasets/`. Don't share.
- **Letting the dataset drift unversioned.** Without a tag (`eval-v3`) it's impossible to say whether a pass-rate jump means "we improved" or "we changed the goldens".
- **Evaluating only on synthetic rows.** Salt the golden set with at least one real production trace per stratum — synthetic data has subtle distribution skew.
