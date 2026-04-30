# Cross-cutting: Testing Strategy

**Concern:** Three-tier test strategy that validates agent behavior without flaky LLM-dependent suites blocking CI.
**Library:** `pytest` + `deepeval` (Py) / `vitest` (TS)
**Lives in:** Inline below (formerly `common/python/agent_common/testing/` and `common/typescript/src/testing/`)

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

Validate that mock fixtures produce correct response shapes and that the mock client cycles through predefined responses.

## Reference Implementation

<details>
<summary>Python — <code>fixtures.py</code></summary>

```python
"""Shared pytest fixtures and test utilities for agent-deployments prototypes."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock


def mock_llm_response(content: str = "Hello from mock LLM", **kwargs: Any) -> MagicMock:
    """Create a mock LLM response object."""
    message = MagicMock()
    message.content = content
    message.role = "assistant"
    message.tool_calls = kwargs.get("tool_calls", [])

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = kwargs.get("finish_reason", "stop")

    response = MagicMock()
    response.choices = [choice]
    response.model = kwargs.get("model", "mock-model")
    response.usage = MagicMock(
        prompt_tokens=kwargs.get("prompt_tokens", 10),
        completion_tokens=kwargs.get("completion_tokens", 20),
        total_tokens=kwargs.get("total_tokens", 30),
    )

    return response


def mock_llm_client(responses: list[str] | None = None) -> AsyncMock:
    """Create a mock async LLM client that returns predefined responses."""
    _responses = responses or ["Mock response"]
    _call_count = 0

    async def _create(**kwargs: Any) -> MagicMock:
        nonlocal _call_count
        content = _responses[_call_count % len(_responses)]
        _call_count += 1
        return mock_llm_response(content, **kwargs)

    client = AsyncMock()
    client.chat.completions.create = _create
    return client
```

</details>

<details>
<summary>TypeScript — <code>fixtures.ts</code></summary>

```typescript
/**
 * Shared test utilities for agent-deployments prototypes.
 */

export interface MockLlmResponse {
  choices: Array<{
    message: { role: string; content: string; tool_calls?: unknown[] };
    finish_reason: string;
  }>;
  model: string;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

/**
 * Create a mock LLM response object.
 */
export function mockLlmResponse(
  content = "Hello from mock LLM",
  options: {
    model?: string;
    finishReason?: string;
    toolCalls?: unknown[];
  } = {},
): MockLlmResponse {
  return {
    choices: [
      {
        message: {
          role: "assistant",
          content,
          tool_calls: options.toolCalls ?? [],
        },
        finish_reason: options.finishReason ?? "stop",
      },
    ],
    model: options.model ?? "mock-model",
    usage: {
      prompt_tokens: 10,
      completion_tokens: 20,
      total_tokens: 30,
    },
  };
}

/**
 * Create a mock LLM client that returns predefined responses.
 */
export function mockLlmClient(responses: string[] = ["Mock response"]) {
  let callCount = 0;

  return {
    chat: {
      completions: {
        create: async (): Promise<MockLlmResponse> => {
          const content = responses[callCount % responses.length] ?? "";
          callCount++;
          return mockLlmResponse(content);
        },
      },
    },
  };
}
```

</details>
