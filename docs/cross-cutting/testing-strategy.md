# Cross-cutting: Testing Strategy

**Concern:** Three-tier test strategy that validates agent behavior without flaky LLM-dependent suites blocking CI.
**Library:** `pytest` + `deepeval` (Py) / `vitest` (TS)
**Lives in:** `common/python/agent_common/testing/` and `common/typescript/src/testing/`

## The three tiers

```
┌──────────────────────────────────────────────┐
│  Tier 3: Eval (golden datasets)              │  main branch only, real LLM
│  Faithfulness, relevancy, correctness        │
├──────────────────────────────────────────────┤
│  Tier 2: Integration (real LLM)              │  main branch only, ANTHROPIC_API_KEY
│  End-to-end agent flow, actual model calls   │
├──────────────────────────────────────────────┤
│  Tier 1: Unit (mocked LLM)                  │  every PR, fast, deterministic
│  Schema validation, tool logic, API routes   │
└──────────────────────────────────────────────┘
```

| Tier | Runs on | LLM | Speed | What it validates |
|------|---------|-----|-------|-------------------|
| Unit | Every PR | Mocked | < 10s | Schemas, tool functions, route handlers, chunking logic |
| Integration | Main only | Real | 30-60s | Full agent pipeline with actual model calls |
| Eval | Main only | Real | 1-5min | Quality metrics on golden datasets |

## Directory layout

Every prototype follows this structure:

```
# Python
tests/
├── __init__.py
├── unit/
│   ├── __init__.py
│   ├── test_api.py         # Route handler tests
│   ├── test_schemas.py     # Request/response validation
│   └── test_tools.py       # Tool function logic
├── integration/
│   └── __init__.py
└── evals/
    └── __init__.py

# TypeScript
tests/
├── unit/
│   ├── api.test.ts
│   ├── schemas.test.ts
│   └── tools.test.ts
```

## Shared test fixtures

The `common/testing` module provides mock LLM utilities so unit tests never hit a real model:

### Python

```python
from agent_common.testing import mock_llm_response, mock_llm_client

# Single mock response
response = mock_llm_response("The answer is 42", model="claude-sonnet-4-6")
assert response.choices[0].message.content == "The answer is 42"

# Mock client that cycles through predefined responses
client = mock_llm_client(["Response 1", "Response 2"])
result = await client.chat.completions.create()
assert result.choices[0].message.content == "Response 1"
```

### TypeScript

```typescript
import { mockLlmResponse, mockLlmClient } from "@agent-deployments/common";

const response = mockLlmResponse("The answer is 42");
expect(response.choices[0].message.content).toBe("The answer is 42");

const client = mockLlmClient(["Response 1", "Response 2"]);
const result = await client.chat.completions.create();
expect(result.choices[0].message.content).toBe("Response 1");
```

## Running tests

```bash
# Unit tests (every PR)
make test-unit PROTOTYPE=docs-rag-qa TRACK=python

# Integration tests (needs ANTHROPIC_API_KEY)
make test-integration PROTOTYPE=docs-rag-qa TRACK=python

# Eval suite (needs ANTHROPIC_API_KEY)
make eval PROTOTYPE=docs-rag-qa TRACK=python

# All tests
make test PROTOTYPE=docs-rag-qa TRACK=python
```

## CI behavior

Defined in `.github/workflows/ci.yml`:

- **On PR:** Unit tests run. Integration and eval are skipped (no API key, saves cost).
- **On main:** Unit + integration + eval all run with `ANTHROPIC_API_KEY` from GitHub Secrets.
- **Exit code 5** (no tests collected) is treated as success via `|| test $? -eq 5`, handling prototypes where integration/eval tests haven't been written yet.

## Eval datasets

Each prototype includes `eval/dataset.jsonl` with golden input/output pairs:

```jsonl
{"input": "What is MCP?", "expected_output": "MCP is the Model Context Protocol...", "metadata": {}}
```

## Security testing (Promptfoo)

Each prototype includes `eval/promptfoo.yaml` for red-team scans:

```yaml
redteam:
  plugins:
    - prompt-injection
    - jailbreak
    - pii
```

Run via `make security PROTOTYPE=<name>`. Runs on main branch in CI.

## Tests

- **Python:** `common/python/tests/test_testing.py` -- validates mock fixtures
- **TypeScript:** `common/typescript/tests/testing.test.ts` -- validates mock fixtures
