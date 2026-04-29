# Stack pick: Eval Toolchain (DeepEval + RAGAS + Promptfoo)

**Choice:** Three complementary tools, each covering a different eval surface
**Used for:** Agent quality metrics, RAG-specific metrics, and security/red-team scanning

## Why three tools

| Tool | Surface | Language | Runs in |
|------|---------|----------|---------|
| **DeepEval** | General agent eval (faithfulness, relevancy, correctness, hallucination, 50+ metrics) | Python (pytest plugin) | `make eval` / CI |
| **RAGAS** | RAG-specific metrics (context recall, context precision, faithfulness, answer relevancy) | Python | `make eval` (for RAG prototypes) |
| **Promptfoo** | Red-team / security (prompt injection, jailbreak, PII leakage) | Node.js CLI (YAML config) | `make security` / CI |

They don't overlap. DeepEval handles general agent quality, RAGAS adds purpose-built RAG metrics, and Promptfoo handles adversarial testing.

## Why these over alternatives

| Option | Why not |
|--------|---------|
| LangSmith Eval | Tied to LangChain ecosystem; DeepEval is framework-agnostic |
| Arize Phoenix | Strong tracing but weaker on eval metrics vs DeepEval |
| Custom eval scripts | DeepEval's pytest integration and metric library save weeks of work |
| Garak (red-team) | Promptfoo has better YAML ergonomics and broader plugin ecosystem |

## DeepEval

### Setup

```bash
uv add deepeval  # in dev dependencies
```

### Usage in eval tests

```python
from deepeval import assert_test
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase

def test_faithfulness():
    test_case = LLMTestCase(
        input="What is MCP?",
        actual_output="MCP is the Model Context Protocol...",
        retrieval_context=["The Model Context Protocol (MCP) is an open standard..."],
    )
    metric = FaithfulnessMetric(threshold=0.7)
    assert_test(test_case, [metric])
```

### Key metrics

| Metric | What it measures |
|--------|-----------------|
| `FaithfulnessMetric` | Is the output grounded in provided context? |
| `AnswerRelevancyMetric` | Does the output address the input question? |
| `HallucinationMetric` | Does the output contain unsupported claims? |
| `ToolCorrectnessMetric` | Did the agent use the right tools with correct arguments? |

## RAGAS

### Setup

```bash
uv add ragas  # in dev dependencies
```

### Usage

```python
from ragas.metrics import faithfulness, context_recall, context_precision
from ragas import evaluate
from datasets import Dataset

data = Dataset.from_dict({
    "question": ["What is MCP?"],
    "answer": ["MCP is the Model Context Protocol..."],
    "contexts": [["The Model Context Protocol (MCP) is an open standard..."]],
    "ground_truth": ["MCP is an open standard for connecting AI models to external tools."],
})

result = evaluate(data, metrics=[faithfulness, context_recall, context_precision])
```

### When to use

Only for the `docs-rag-qa` prototype (and any future RAG-based prototype). RAGAS metrics specifically measure retrieval + generation quality.

## Promptfoo

### Setup

```bash
npm install -g promptfoo
```

### Configuration

Each prototype includes `eval/promptfoo.yaml`:

```yaml
description: "Security scan for customer-support-triage"

prompts:
  - "{{message}}"

providers:
  - id: http
    config:
      url: http://localhost:8000/triage
      method: POST
      headers:
        Content-Type: application/json
      body:
        message: "{{message}}"
        user_id: "eval-user"

redteam:
  plugins:
    - prompt-injection
    - jailbreak
    - pii
```

### Running

```bash
make security PROTOTYPE=customer-support-triage   # both tracks

# Or directly
promptfoo redteam run --config eval/promptfoo.yaml
```

### What it tests

| Plugin | What it checks |
|--------|---------------|
| `prompt-injection` | Can adversarial prompts override system instructions? |
| `jailbreak` | Can the agent be tricked into bypassing safety guidelines? |
| `pii` | Does the agent leak personally identifiable information? |

## Golden datasets

Each prototype ships `eval/dataset.jsonl` with input/expected-output pairs:

```jsonl
{"input": "What is MCP?", "expected_output": "MCP is the Model Context Protocol...", "metadata": {}}
```

These feed both DeepEval and RAGAS test suites.

## CI integration

In `.github/workflows/ci.yml`:

- **Eval suite** runs on main branch only (requires `ANTHROPIC_API_KEY`): `make eval`
- **Security scan** runs on main branch only: `make security`
- Both use `continue-on-error: true` to avoid blocking merges on flaky LLM outputs

## Where used in repo

- **`eval/dataset.jsonl`** -- in every prototype (both tracks)
- **`eval/promptfoo.yaml`** -- in every prototype (both tracks)
- **`tests/evals/`** -- Python eval test files (using DeepEval/RAGAS)
- **CI** -- automated via GitHub Actions
