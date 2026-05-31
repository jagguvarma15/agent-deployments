# Evals (Promptfoo)

Declarative regression evals for this agent. Emitted by the `eval.promptfoo` capability.

## Run locally

```bash
cd evals
npx promptfoo eval         # run the suite; writes last-run.json
npx promptfoo view         # open the result viewer in a browser
```

The first `agent-scaffold up` runs this automatically and stores the pass-rate as the baseline in the project manifest. Subsequent runs flag regressions when the rate drops below baseline.

## Env vars

| Var | Required | Purpose |
|-----|----------|---------|
| `ANTHROPIC_API_KEY` | Yes | Provider credential. The eval skips with a clear message if absent. |

Set it in `.env.local` at the project root or export it before invoking `npx promptfoo eval`.

## Layout

- `promptfooconfig.yaml` — top-level config. Provider, tests pointer, retry policy, output path. Edit to change the model.
- `cases.yaml` — three recipe-agnostic starter cases (greeting, refusal, tool-call). Don't edit; the capability owns these.
- `cases.recipe.yaml` — recipe-specific cases emitted from the golden dataset during generation. **Add domain cases here.**
- `last-run.json` — written by each `npx promptfoo eval` run. Diffed against the manifest baseline.

## Adding a case

Append to `cases.recipe.yaml`:

```yaml
- description: "short, action-oriented label"
  vars:
    prompt: "the input the agent will see"
  assert:
    - type: llm-rubric
      value: "what a passing answer looks like, in prose"
```

Use `type: equals` / `contains` / `regex` for deterministic checks, `llm-rubric` for judged ones. See the [Promptfoo reference](https://promptfoo.dev/docs/configuration/reference/) for the full assertion vocabulary.

## CI

Wire `npx promptfoo eval --output evals/last-run.json` into the workflow. Fail the job if the pass-rate falls below the stored baseline.
