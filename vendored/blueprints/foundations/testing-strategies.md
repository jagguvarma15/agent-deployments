# Testing Strategies for LLM Systems

Testing agent systems is fundamentally different from testing conventional software.
The core challenge: LLM outputs are probabilistic, not deterministic. The same input
can produce different outputs across calls, models, temperatures, and time. Traditional
assertion-based testing breaks down quickly.

This guide covers a layered testing approach that works for all patterns in this repo.

---

## The Testing Pyramid for LLM Systems

```
         ┌─────────────────┐
         │   Evaluation    │  ← Did the system produce good output? (LLM-as-judge, human review)
         ├─────────────────┤
         │   Integration   │  ← Does the system work end-to-end with a real LLM?
         ├─────────────────┤
         │   Component     │  ← Does each piece work in isolation? (mock LLM)
         ├─────────────────┤
         │      Unit       │  ← Does the logic work independently of the LLM?
         └─────────────────┘
```

Each layer has a different purpose, cost, and feedback speed. Run lower layers frequently
and cheaply; run upper layers less often and more deliberately.

---

## Layer 1: Unit Tests (Logic Only)

Test everything that does not involve an LLM call. These tests are fast, free, and
deterministic. They are often skipped in LLM projects but cover a significant surface area.

**What to test:**

- Parsing functions that extract structured data from LLM output strings
- Gate / validation functions (is this output long enough? is it valid JSON?)
- Context accumulation logic (is the message history built correctly?)
- Tool dispatch routing (does the dispatcher call the right function?)
- Token counting and truncation logic
- Retry and error handling paths

### Example: testing a ReAct response parser

```python
def test_parse_action():
    raw = "Thought: I need to search.\nAction: search\nAction Input: python agents"
    result = parse_react_response(raw)
    assert result.thought == "I need to search."
    assert result.action == "search"
    assert result.action_input == "python agents"
    assert result.final_answer is None

def test_parse_final_answer():
    raw = "Thought: I know the answer.\nFinal Answer: ReAct combines reasoning and acting."
    result = parse_react_response(raw)
    assert result.final_answer == "ReAct combines reasoning and acting."
    assert result.action is None

def test_parse_malformed_response():
    raw = "Here is my response: I think the answer is yes."
    result = parse_react_response(raw)
    assert result.parse_failed is True
```

### Example: testing a routing classifier dispatcher

```python
def test_route_dispatch_billing():
    result = ClassificationResult(route="billing", confidence=0.92)
    handler = router.get_handler(result)
    assert handler.name == "billing"

def test_route_dispatch_low_confidence_uses_fallback():
    result = ClassificationResult(route="billing", confidence=0.41)
    handler = router.get_handler(result, confidence_threshold=0.6)
    assert handler.name == router.fallback_route
```

---

## Layer 2: Component Tests (Mock LLM)

Test each component — the chain, the agent loop, the evaluator — with a mock LLM that
returns scripted, deterministic responses. This lets you verify control flow, state
management, and error handling without making real API calls.

**The MockLLM pattern:**

```python
class ScriptedLLM:
    """Returns pre-written responses in sequence, regardless of input."""
    def __init__(self, responses: list[str]):
        self._responses = iter(responses)

    def generate(self, messages: list[dict], **kwargs) -> str:
        return next(self._responses)


class ConditionalLLM:
    """Returns different responses based on a keyword in the last message."""
    def __init__(self, rules: dict[str, str], default: str = ""):
        self._rules = rules
        self._default = default

    def generate(self, messages: list[dict], **kwargs) -> str:
        last = messages[-1]["content"].lower()
        for keyword, response in self._rules.items():
            if keyword in last:
                return response
        return self._default
```

**What to test with mock LLMs:**

- Does the chain run the correct number of steps?
- Does the ReAct loop terminate on "Final Answer:"?
- Does the evaluator loop stop early when the evaluator returns PASS?
- Does the max_steps / max_iterations guard trigger correctly?
- Does the orchestrator handle a JSON parse failure gracefully?
- Is the message history built in the right order?

### Example: testing a prompt chain with a scripted LLM

```python
def test_chain_runs_all_steps():
    llm = ScriptedLLM(["extracted facts", "ranked facts", "formatted checklist"])
    chain = PromptChain(llm=llm, steps=[step1, step2, step3])
    result = chain.run("raw input")
    assert result.success is True
    assert len(result.step_outputs) == 3
    assert result.output == "formatted checklist"

def test_chain_halts_on_gate_failure():
    llm = ScriptedLLM(["too short"])  # gate requires len > 50
    chain = PromptChain(llm=llm, steps=[step_with_gate])
    result = chain.run("input")
    assert result.success is False
    assert result.failed_at == "extract"
    assert len(result.step_outputs) == 0  # gate rejected before storing
```

### Example: testing ReAct terminates with a guard

```python
def test_react_stops_at_max_steps():
    # LLM always wants to call a tool, never produces Final Answer
    llm = ScriptedLLM([
        "Thought: search\nAction: search\nAction Input: x"
    ] * 20)  # more than max_steps
    agent = ReActAgent(llm=llm, tools=[mock_tool], max_steps=5)
    result = agent.run("task")
    assert result.stopped_by_guard is True
    assert len(result.steps) == 5
```

---

## Layer 3: Integration Tests (Real LLM, Controlled Scenarios)

Run the full system with a real LLM against a curated set of test scenarios. These tests
are slower and cost real tokens, but they catch the class of bugs that only appear when the
actual model is involved: prompt failures, format drift, context sensitivity, model version
regressions.

**Design principles for integration test scenarios:**

- Cover the happy path (normal successful execution)
- Cover boundary conditions (empty input, very long input, input in a different language)
- Cover known failure modes from your observability data
- Keep the number of scenarios small but representative (10-30 is usually enough)
- Version-control the scenarios alongside the code

**A good integration test scenario for a RAG pipeline:**

```python
RAG_TEST_CASES = [
    {
        "id": "rag_direct_answer",
        "question": "What is the company's parental leave policy?",
        "documents": [HANDBOOK_PARENTAL_LEAVE_PAGE],
        "expected_contains": ["16 weeks", "primary caregiver"],
        "expected_not_contains": ["I don't have information"],
    },
    {
        "id": "rag_out_of_scope",
        "question": "What is the CEO's home address?",
        "documents": [HANDBOOK_PARENTAL_LEAVE_PAGE],
        "expected_contains": ["don't have information", "not in the document"],
        "expected_not_contains": [],  # should not hallucinate an address
    },
    {
        "id": "rag_partial_answer",
        "question": "What is the policy for remote work in other countries?",
        "documents": [HANDBOOK_REMOTE_WORK_PAGE],  # only covers domestic remote
        "expected_contains": ["not covered", "contact HR", "additional approval"],
    },
]
```

**Running integration tests with retries:**

LLM responses have variance. A good integration test runs each scenario 3-5 times and
checks that the assertion passes on at least N of those runs, rather than requiring 100%
consistency.

```python
def assert_with_retries(fn, assertion, retries=3, min_pass=2):
    passes = sum(1 for _ in range(retries) if assertion(fn()))
    assert passes >= min_pass, f"Passed {passes}/{retries} times, required {min_pass}"
```

---

## Layer 4: Evaluation (Output Quality)

Evaluation answers a different question than testing: not "did the system work?" but
"did the system produce a good output?" This layer is more subjective and more expensive,
but it is the only way to measure actual quality.

### LLM-as-judge

Use a capable LLM to evaluate outputs against a rubric. This is faster than human review
and more consistent than keyword matching.

```python
JUDGE_PROMPT = """
You are evaluating the quality of an AI response.

Evaluation criteria:
1. Accuracy: Is every factual claim correct?
2. Completeness: Does the response address all parts of the question?
3. Clarity: Is the response easy to understand?
4. Conciseness: Is the response appropriately brief without losing important content?

Score each criterion from 1 to 5.
Flag any factual errors you detect.

Question: {question}
Response to evaluate: {response}

Respond in JSON:
{
  "accuracy": {1-5},
  "completeness": {1-5},
  "clarity": {1-5},
  "conciseness": {1-5},
  "overall": {1-5},
  "errors": ["list any factual errors, or empty array if none"],
  "reasoning": "one sentence explaining the overall score"
}
"""
```

**Important caveats for LLM-as-judge:**

- Use a different model as the judge than the one being evaluated, to reduce self-evaluation bias
- Judges have their own biases (preference for longer responses, certain styles)
- Calibrate: run the judge on known-good and known-bad examples and verify it scores them correctly
- Use the judge score as a relative signal, not an absolute quality measure

### Pairwise comparison

Instead of absolute scoring, compare two outputs and ask which is better. This is more
reliable because it is easier for a model to say "A is better than B" than to assign
a precise numeric score.

```python
PAIRWISE_PROMPT = """
You are comparing two AI responses to the same question.

Question: {question}

Response A:
{response_a}

Response B:
{response_b}

Which response better addresses the question? Consider accuracy, completeness, and clarity.

Respond with exactly one word: A or B.
If they are equivalent, respond: TIE
"""
```

### Reference-based evaluation

When you have known-good reference answers, compare generated output to them.
Exact match is too strict for LLM outputs; use semantic similarity or a judge.

```python
def evaluate_against_reference(generated: str, reference: str, judge_llm) -> float:
    """Returns a 0-1 score of how well generated matches reference semantically."""
    prompt = f"""
    On a scale of 0.0 to 1.0, how semantically equivalent are these two texts?
    0.0 = completely different meaning
    1.0 = same information, possibly different wording

    Text A: {reference}
    Text B: {generated}

    Respond with a single number between 0.0 and 1.0.
    """
    raw = judge_llm.generate([{"role": "user", "content": prompt}])
    return float(raw.strip())
```

---

## Regression Testing

Catch quality regressions when prompts, models, or dependencies change.

**What triggers a regression test run:**
- Any change to a system prompt
- Any change to the LLM model version or parameters
- Any change to tool implementations
- Any change to context injection or retrieval logic
- Dependency upgrades (LLM SDK, vector store library)

**What a regression suite looks like:**

A small set of golden examples — input/output pairs where you have verified the output is
correct and representative. On each change, run the suite and compare the new outputs to
the golden outputs.

```python
GOLDEN_EXAMPLES = [
    {
        "id": "react_simple_search",
        "input": "What year was Python first released?",
        "expected_tools_used": ["search"],
        "expected_answer_contains": ["1991"],
        "max_steps": 3,
    },
    {
        "id": "react_math_calculation",
        "input": "What is 15% of 840?",
        "expected_tools_used": ["calculator"],
        "expected_answer_contains": ["126"],
        "max_steps": 2,
    },
]
```

**Snapshot testing for prompts:**

Store the rendered prompts (after variable substitution) and compare them on each run.
This catches unintended prompt changes that result from code refactors.

```python
def test_system_prompt_unchanged():
    agent = ReActAgent(llm=MockLLM(), tools=standard_tools)
    rendered = agent._build_system()
    assert rendered == GOLDEN_SYSTEM_PROMPT, (
        "System prompt changed. If intentional, update GOLDEN_SYSTEM_PROMPT."
    )
```

---

## Pattern-Specific Testing Notes

### Prompt Chaining
- Test each step independently with a unit test before testing the full chain
- Test gate boundary conditions: what is the minimum output that passes? what always fails?
- Test that context from step N is correctly available in step N+1

### Parallel Calls
- Test that all branches complete, not just that the aggregation returns something
- Test the partial failure path: if one branch fails, does the aggregation still run?
- Test that branch order is preserved in the aggregated output

### ReAct
- Test the loop termination condition with a scripted LLM
- Test that the max_steps guard fires at exactly max_steps, not before or after
- Test the parse fallback: if the LLM produces malformed output, does the agent recover?
- Test tool error handling: if a tool raises an exception, does the agent receive a useful error message?

### RAG
- Test retrieval separately from generation: assert that the right chunks are retrieved for known queries
- Test the no-results path: when no chunks are above the threshold, does the fallback work?
- Test chunk ordering: does a more relevant chunk actually score higher than a less relevant one?

### Evaluator-Optimizer / Reflection
- Test that the loop exits on the first PASS, not after all iterations
- Test the score threshold boundary: just above and just below the threshold
- Test that the generator actually uses the feedback (check that specific issues from the critique are addressed in the revision)

### Routing
- Test classification for each route with representative examples
- Test the low-confidence fallback path explicitly
- Test with ambiguous inputs that could plausibly match multiple routes
- Test that a hallucinated route name triggers the fallback, not a crash

### Multi-Agent
- Test the supervisor's done signal: does the system terminate cleanly when `{"done": true}` is returned?
- Test the max_rounds guard
- Test that agent outputs are correctly accumulated into the supervisor's context
- Test what happens when a sub-agent returns an error

---

## Testing Checklist

Before shipping any LLM-powered component to production, verify:

- [ ] Unit tests cover all parsing, validation, and dispatch logic
- [ ] Mock LLM tests verify control flow for happy path and common failure modes
- [ ] Integration tests run against at least 10 curated scenarios with a real LLM
- [ ] Loop guards are tested: max_steps, max_iterations, max_rounds
- [ ] Error paths are tested: tool failure, LLM timeout, parse failure
- [ ] A golden example set exists for regression detection
- [ ] An LLM-as-judge evaluation is defined with a calibrated rubric
- [ ] The test suite runs on every CI push (unit + mock tests only; integration tests on merge)
