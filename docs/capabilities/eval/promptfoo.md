---
id: eval.promptfoo
kind: eval
layer: eval
provides: [llm_eval, regression_check]
env_vars: [ANTHROPIC_API_KEY]
docker: null
probe: null
bootstrap_step: bootstrap_evals
provisioning_time: instant
cost_tier: per-call
est_tokens: 700
card:
  name: Promptfoo
  description: "YAML-first LLM evaluation harness with provider matrix, LLM-judge grading, and CI gating."
  capabilities_provided: [llm_eval, regression_check, ci_gating]
  required_credentials: [ANTHROPIC_API_KEY]
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

## Contract

The capability emits three files into the generated project under `evals/`:

| Emitted file | Role |
|---|---|
| `evals/promptfooconfig.yaml` | Top-level config: providers, tests file pointer, output path, retry policy. |
| `evals/cases.yaml` | Three recipe-agnostic starter cases (greeting, refusal, tool-call). |
| `evals/README.md` | One-page operator guide: how to run locally, expected env vars, where to add domain cases. |

Recipe-specific cases land in a sibling `evals/cases.recipe.yaml` (LLM emits during generation from the recipe's golden dataset).

## Local run

```bash
cd evals
npx promptfoo eval
npx promptfoo view   # opens the result viewer in a browser
```

`npx promptfoo eval` writes `evals/last-run.json`; `bootstrap_evals` diffs new runs against this file's stored baseline. To re-baseline, delete `evals/last-run.json` and re-run.

## Bootstrap

`bootstrap_evals` runs an initial eval on first `agent-scaffold up`, capturing pass-rate as the baseline.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `ANTHROPIC_API_KEY` | — | Provider credential. Eval skips with a clear message if absent. |

## Client integration

**Shell (the canonical entry point):**

```bash
cd evals
npx promptfoo eval --config promptfooconfig.yaml --output last-run.json
```

**CI gate (GitHub Actions):**

```yaml
- name: Run evals
  run: |
    cd evals
    npx promptfoo eval --output last-run.json
    pass_rate=$(jq '[.results.results[] | select(.success)] | length / ([.results.results | length]) * 100' last-run.json)
    if (( $(echo "$pass_rate < 90" | bc -l) )); then
      echo "Pass rate $pass_rate% below 90% threshold"
      exit 1
    fi
```

## Cloud / production

Dev/CI tool — no production deployment. For richer dashboards, push results to [Promptfoo Cloud](https://promptfoo.dev/) or self-host the viewer.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Missing API key for provider 'anthropic'` | `ANTHROPIC_API_KEY` not in env | `export ANTHROPIC_API_KEY=sk-ant-...` or load via direnv |
| LLM-judge cases all fail | Judge model unavailable / rate-limited | Reduce concurrency in `promptfooconfig.yaml` `defaultTest.options.maxConcurrency` |
| Pass-rate drop unrelated to changes | Model provider drift between runs | Pin `model: claude-sonnet-4-6` exactly; do not use floating aliases |
| `npx` slow on first run | Promptfoo not cached | One-time install: `pnpm add -D promptfoo` in the project root |

## See also

- [`cross-cutting/testing-strategy.md`](../../cross-cutting/testing-strategy.md) — three-tier test strategy
- [`docs/recipes/restaurant-rebooking.md`](../../recipes/restaurant-rebooking.md) — recipe that declares `eval.promptfoo`
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
