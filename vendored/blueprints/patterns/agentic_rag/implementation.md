# Agentic RAG — Implementation

> Code variants under `code/python/` are not yet shipped; the pseudocode here is framework-agnostic and mirrors [`schemas/state.py`](schemas/state.py).

## Runner shape

The runner orchestrates the loop. It's stateless across calls but maintains per-question state inside one call.

```python
def answer(question, state=None):
    state = state or AgenticRagState(question=question)

    state.subquestions = decompose(question)
    if not state.subquestions:
        state.subquestions = [SubQuestion(text=question)]

    for sq in state.subquestions:
        sq.evidence = run_retrieval_loop(sq)

    if any(sq.evidence is None for sq in state.subquestions):
        return abstain(state, reason="insufficient_evidence_after_retries")

    conflicts = cross_source_consistency(state.subquestions)
    draft = compose_answer(question, state.subquestions, conflicts)

    verification = verify_citations(draft, state)
    if verification.has_ungrounded_claims:
        return retry_or_abstain(state, draft, verification)

    return AgenticRagResult(
        answer=draft.answer,
        citations=draft.citations,
        confidence=draft.confidence,
        conflicts=conflicts,
        trace=state.trace_summary(),
    )
```

## Retrieval loop per sub-question

```python
def run_retrieval_loop(sub_question):
    attempts = []
    refined = sub_question.text
    for attempt_idx in range(MAX_ATTEMPTS):
        source_name = planner.choose_source(refined, sources, attempts)
        chunks = source_router.retrieve(source_name, refined, k=TOP_K)
        scored = relevance_scorer.score(refined, chunks)
        attempt = RetrievalAttempt(
            attempt=attempt_idx,
            query=refined,
            source=source_name,
            chunks=scored,
        )
        attempts.append(attempt)

        verdict = sufficiency_reflector.check(refined, scored)
        attempt.verdict = verdict

        if verdict.kind == "sufficient":
            sub_question.evidence = scored
            sub_question.attempts = attempts
            return scored

        refined = query_reformulator.refine(refined, verdict.missing, attempts)
        # Optionally rotate to a different source on the next attempt.

    sub_question.attempts = attempts
    return None   # cap hit
```

The loop carries `attempts` forward so the reformulator can avoid repeating prior queries.

## Source adapter interface

Every source implements one shape so the router doesn't case on type:

```python
class SourceAdapter(Protocol):
    name: str
    kind: Literal["vector", "sql", "api", "web"]
    description: str
    when_to_use: str
    when_not_to_use: str

    def retrieve(self, query: str, k: int) -> list[EvidenceChunk]: ...
```

`EvidenceChunk` carries the data plus the metadata the citation verifier needs:

```python
@dataclass
class EvidenceChunk:
    chunk_id: str               # stable per-source id; e.g. "handbook:§3.2:para_4"
    source: str                 # source adapter name
    text: str                   # retrieved content
    metadata: dict              # provenance, timestamps, version
    embedding_score: float | None  # for vector sources
```

### Vector adapter

Standard embedding + top-K query. Used as-is from baseline RAG. The `chunk_id` becomes `f"{source}:{doc_id}:{chunk_offset}"`.

### SQL adapter

LLM translates the natural-language query into a SQL statement against a schema description. The rows become chunks with `chunk_id = f"{source}:row:{primary_key}"`. The schema description must be in the source adapter's `description` so the translator knows what's queryable.

### API adapter

Maps the natural-language query to a structured API call (often via a tool-call schema). The response payload becomes chunks; `chunk_id` is typically the API's resource id.

### Web adapter

Calls a web search API and (optionally) fetches the top results. Each result is a chunk; `chunk_id = f"web:{search_id}:{result_index}"`. Web chunks are higher-risk for injection — route them through the quarantined LLM before they reach the answer composer.

## Citation tracking

The composer's prompt enforces citation discipline:

```
You must cite every factual claim with a marker like [source:chunk_id].
Multiple citations on one claim: [source_a:id1, source_b:id2].
If a claim is not backed by a retrieved chunk, OMIT THE CLAIM rather than write it without a citation.
```

The verifier then parses the markers and resolves them:

```python
def verify_citations(draft, state):
    valid_ids = {chunk.chunk_id for sq in state.subquestions for chunk in (sq.evidence or [])}
    markers = parse_citation_markers(draft.answer)
    ungrounded = [m for m in markers if m not in valid_ids]
    claims_without_citation = find_factual_claims_missing_citation(draft.answer)
    return VerificationResult(
        ungrounded_citation_ids=ungrounded,
        unsupported_claims=claims_without_citation,
    )
```

`find_factual_claims_missing_citation` is itself usually an LLM call: "Identify any sentence in this draft that asserts a fact but has no [source:id] marker." Imperfect but high signal.

## Per-tier model selection

Agentic RAG fans out across many LLM calls. Per-tier selection is the dominant cost lever:

| Step | Suggested tier | Why |
|---|---|---|
| Decomposition | Sonnet | Structured output; modest reasoning |
| Source routing | Haiku | Pick one of N from descriptions |
| SQL translation (SQL adapter) | Sonnet | Schema-aware code generation |
| Relevance scoring | Haiku | Classify per chunk |
| Sufficiency reflection | Sonnet | The cost-of-error step |
| Query reformulation | Sonnet | Needs to understand the gap |
| Cross-source consistency | Sonnet | Compare evidence pieces |
| Answer composition | Sonnet or Opus | The user sees this output |
| Citation verification | Haiku | Re-read draft and match markers |

A reasonable production setup uses Sonnet as the default with Haiku-class for the chatty scoring/verification passes.

## Integration with reflection

The sufficiency reflector and the citation verifier are reflection components. If your codebase already has a reflection harness, agentic RAG is a specialization — the harness owns the loop, and the retrievals + cross-source check are the loop body.

## Integration with sub-agents

When sub-questions are heavy (each requires a multi-step research pass), spawn a sub-agent per sub-question:

```python
futures = [
    spawn("agentic-rag-researcher", task=sq.text, context_envelope={"sources": source_registry})
    for sq in state.subquestions
]
results = await all(futures)
for sq, result in zip(state.subquestions, results):
    sq.evidence = result.payload["evidence"]
    sq.attempts = result.payload["attempts"]
```

This is the deep-agents shape applied to RAG. The planner becomes a thin top-level loop; the work happens in role-scoped sub-agents.

## Pitfalls

- **Over-decomposing simple questions.** Every decomposed sub-question pays the full retrieval-loop cost. Decompose only when needed.
- **Letting reformulation loops repeat queries.** Without `attempts_so_far`, the reformulator may produce the same query twice. Always pass the history.
- **No abstention policy.** Without it, the agent generates an answer from the partial / wrong chunks it did retrieve and writes confident hallucinations.
- **Citation markers parseable in two ways.** Pick a single marker syntax and reject other shapes; otherwise the verifier silently drops markers.
- **Untrusted web chunks reaching the composer raw.** Always summarize web chunks through a quarantined LLM before they reach the privileged composer. See [Guardrails](../../modifiers/guardrails/overview.md).
- **Single source despite registering multiple.** The planner converges on one source if its description is stronger than the rest. Audit routing distribution.
- **Recall measured but not precision.** "Did we retrieve the right chunk?" is recall. "Are the chunks we retrieved actually relevant?" is precision. Both matter; uneven measurement biases tuning.

## Testing

- **Per-sub-question fixture suite.** Each sub-question has expected source + expected chunk ids. Tests assert routing and retrieval.
- **End-to-end golden set.** Compound questions with expected answers AND expected citations. Tests assert both the answer matches and the citations are valid.
- **Adversarial corpus.** RAG-poisoning samples (planted misleading docs) — tests assert cross-source consistency catches them.
- **Abstention test.** Questions designed to fail retrieval; tests assert abstention with reason rather than silent guessing.
- **Citation precision test.** For a sample of generated answers, manually label whether each citation actually supports the cited claim; track over time.

## What we deliberately don't ship

- A specific embedding model. Provider-agnostic; pick per cost/quality.
- A specific re-ranker. The relevance scorer described above is LLM-based; a learned re-ranker is a swappable upgrade.
- A SQL translation library. The SQL adapter is sketched; production systems should use a vetted text-to-SQL approach with safe execution sandboxes.
