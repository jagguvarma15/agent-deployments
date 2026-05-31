---
id: eval.promptfoo
kind: eval
provides: [llm_eval, regression_check]
env_vars: [ANTHROPIC_API_KEY]
docker: null
probe: null
bootstrap_step: bootstrap_evals
emit_files:
  - source: templates/promptfoo/**
    dest: evals/
deploy_configs: []
docs: |
  Promptfoo eval harness. Generated project gets evals/promptfooconfig.yaml +
  evals/cases.yaml stubs; `agent-scaffold eval` shells out to `npx promptfoo
  eval` and renders pass/fail + LLM-judge scores.
---

# Capability: eval.promptfoo

> Vendor reference: https://promptfoo.dev/docs/configuration/reference/.

**Used for:** declarative LLM regression evals — provider × prompt × cases matrix, pass/fail + LLM-judge scoring, baseline tracking across runs.

## Why pick this

Promptfoo is YAML-first, provider-agnostic, and runs locally via `npx` (no daemon, no service to host). It's the right default when you want to commit a small set of evals to the repo and run them in CI alongside unit tests. Pick a heavier harness (`eval.deepeval`, `eval.ragas`) only when you need RAG-specific metrics or programmatic test composition beyond what YAML expresses.

## Contract

The capability emits three files into the generated project under `evals/`:

| Emitted file | Role |
|---|---|
| `evals/promptfooconfig.yaml` | Top-level config: providers, tests file pointer, output path, retry policy. |
| `evals/cases.yaml` | Three recipe-agnostic starter cases (greeting, refusal, tool-call). Always present. |
| `evals/README.md` | One-page operator guide: how to run locally, expected env vars, where to add domain cases. |

Recipe-specific cases land in a sibling **`evals/cases.recipe.yaml`** — the LLM emits it from the recipe's golden dataset during generation. `promptfooconfig.yaml` references both files under `tests:` so the two sets compose without either side editing the other.

The `tests:` block resolves its provider line from project env (`ANTHROPIC_API_KEY` is the only required var). The `bootstrap_evals` step runs an initial eval on first `agent-scaffold up` and writes the baseline summary to the project manifest so subsequent runs detect regressions (pass-rate drop, per-case status change).

## Local run

```bash
cd evals
npx promptfoo eval
npx promptfoo view   # opens the result viewer in a browser
```

`npx promptfoo eval` writes `evals/last-run.json`; the bootstrap step diffs new runs against this file's stored baseline (after `agent-scaffold up` succeeds, the current pass-rate becomes the baseline). To re-baseline intentionally, delete `evals/last-run.json` and re-run.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `ANTHROPIC_API_KEY` | — | Provider credential. Required; the eval skips with a clear message if absent. |

## Cloud / production

Promptfoo is a dev/CI tool — there is no "production" deployment. In CI, run `npx promptfoo eval --output evals/last-run.json` and fail the job if the pass-rate drops below the manifest baseline. For richer dashboards, push results to [Promptfoo Cloud](https://promptfoo.dev/) or self-host their viewer separately.

## When to swap it

- **→ `eval.deepeval`** for RAG-specific metrics (faithfulness, answer relevancy, contextual precision).
- **→ `eval.ragas`** for academic RAG benchmarking with Python-native composition.

## See also

- `cross-cutting/testing-strategy.md` — three-tier test strategy (unit / integration / eval).
- `docs/recipes/restaurant-rebooking.md` — first recipe to declare `eval.promptfoo`.
