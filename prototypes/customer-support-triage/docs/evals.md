# Evaluation — customer-support-triage

## What's evaluated

| Metric | Tool | Target |
|--------|------|--------|
| Intent classification accuracy | DeepEval | >= 90% |
| Tool-call correctness | DeepEval | >= 85% |
| Prompt injection resistance | Promptfoo | No criticals |
| PII leakage | Promptfoo | No criticals |

## Golden dataset

Located at `eval/dataset.jsonl`. 100 labeled examples across intents:

```json
{"input": "I was charged twice for my subscription", "expected_intent": "billing", "expected_tool": "stripe_lookup"}
{"input": "How do I reset my password?", "expected_intent": "account", "expected_tool": null}
{"input": "The API returns 500 errors when I send large payloads", "expected_intent": "technical", "expected_tool": "kb_search"}
```

## Running evals

```bash
make eval PROTOTYPE=customer-support-triage TRACK=python
make eval PROTOTYPE=customer-support-triage TRACK=typescript
```

## Security scan

```bash
make security PROTOTYPE=customer-support-triage
```
