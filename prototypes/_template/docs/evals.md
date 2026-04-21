# Evaluation — <prototype-name>

## What's evaluated

| Metric | Tool | Target |
|--------|------|--------|
| | DeepEval | |

## Golden dataset

Located at `eval/dataset.jsonl`. Each entry contains:

```json
{
  "input": "...",
  "expected_output": "...",
  "metadata": {}
}
```

## Running evals

```bash
# From the prototype directory
make eval PROTOTYPE=<prototype-name> TRACK=python    # or typescript

# Or directly
cd python && uv run pytest tests/evals -v
cd typescript && pnpm run test:eval
```

## Security scan (Promptfoo)

```bash
make security PROTOTYPE=<prototype-name>
```

Scans for: prompt injection, jailbreaks, PII leakage.
