"""Canonical Pydantic v2 state schema for the Agentic RAG pattern.

The agent decomposes the question into sub-questions, plans per-sub-question
retrieval across registered sources, reflects on sufficiency and reformulates
queries, then composes a citation-bound answer that a verifier checks.
Self-contained — no cross-pattern imports.

See ``../design.md`` for the prose definition of each field.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

SourceKind = Literal["vector", "sql", "api", "web"]
SufficiencyVerdictKind = Literal["sufficient", "insufficient"]
QuestionOutcome = Literal["answered", "abstained", "escalated"]


class SourceConfig(BaseModel):
    """One entry in the source registry. The planner reads these to route."""

    name: str = Field(description="Stable source id; appears in citations.")
    kind: SourceKind = Field(description="Adapter implementation class.")
    description: str = Field(description="What this source covers; the planner reads this for routing.")
    when_to_use: str | None = Field(default=None)
    when_not_to_use: str | None = Field(default=None)


class EvidenceChunk(BaseModel):
    """One retrieved chunk from a source. Cited from the final answer."""

    chunk_id: str = Field(description="Stable id of the form 'source:doc:offset' or 'source:row_id'.")
    source: str = Field(description="Matches SourceConfig.name.")
    text: str = Field(description="The retrieved content. Treat as untrusted.")
    metadata: dict[str, object] = Field(default_factory=dict)
    embedding_score: float | None = Field(default=None, ge=0.0, le=1.0)
    relevance_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="LLM-scored relevance after retrieval.",
    )
    relevance_label: Literal["relevant", "partially_relevant", "irrelevant"] | None = Field(default=None)


class SufficiencyVerdict(BaseModel):
    """The sufficiency reflector's output for one (sub-question, retrieved evidence) pair."""

    kind: SufficiencyVerdictKind
    missing: str | None = Field(
        default=None,
        description="When insufficient, a short description of what is missing; drives reformulation.",
    )
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class RetrievalAttempt(BaseModel):
    """One pass through the per-sub-question retrieval loop."""

    attempt: int = Field(ge=0, description="0-indexed attempt counter.")
    query: str = Field(description="The exact query that went to the source adapter.")
    source: str = Field(description="Source name; matches SourceConfig.name.")
    chunks: list[EvidenceChunk] = Field(default_factory=list)
    verdict: SufficiencyVerdict | None = Field(default=None)
    duration_ms: int = Field(default=0, ge=0)


class SubQuestion(BaseModel):
    """One sub-question produced by the decomposer (or the question itself when simple)."""

    subquestion_id: str
    text: str = Field(description="The sub-question text.")
    routing_hint: str | None = Field(
        default=None,
        description="Optional planner-emitted hint about which source(s) to try.",
    )
    attempts: list[RetrievalAttempt] = Field(default_factory=list)
    evidence: list[EvidenceChunk] | None = Field(
        default=None,
        description="Final accepted chunks; None when the sub-question failed to ground.",
    )

    @property
    def grounded(self) -> bool:
        return self.evidence is not None and len(self.evidence) > 0


class Citation(BaseModel):
    """One citation marker resolved to a retrieved chunk."""

    marker: str = Field(description="The string used in the answer, e.g. '[handbook:§3.2]'.")
    chunk_id: str = Field(description="Resolves to an EvidenceChunk.chunk_id.")
    relevance_score: float | None = Field(default=None, ge=0.0, le=1.0)


class CrossSourceConflict(BaseModel):
    """A recorded disagreement between sources for one sub-question."""

    subquestion_id: str
    sources: list[str]
    summary: str = Field(description="Short description of the conflict.")
    resolution: Literal["cite_both", "majority", "escalated"] = Field(
        description="How the composer handled the conflict.",
    )


class VerificationResult(BaseModel):
    """Citation verifier output."""

    pass_: bool = Field(alias="pass", description="True when every claim is cited and every citation resolves.")
    ungrounded_citation_ids: list[str] = Field(
        default_factory=list,
        description="Citation markers that did not resolve to any retrieved chunk.",
    )
    unsupported_claims: list[str] = Field(
        default_factory=list,
        description="Claims in the draft that have no citation marker.",
    )

    model_config = {"populate_by_name": True}


class AgenticRagState(BaseModel):
    """Per-question state. Held in memory across the runner's sub-steps."""

    question_id: str
    question: str
    sources: list[SourceConfig] = Field(default_factory=list)
    subquestions: list[SubQuestion] = Field(default_factory=list)
    conflicts: list[CrossSourceConflict] = Field(default_factory=list)
    draft_answer: str | None = Field(default=None)
    citations: list[Citation] = Field(default_factory=list)
    verification: VerificationResult | None = Field(default=None)
    outcome: QuestionOutcome | None = Field(default=None)
    abstention_reason: str | None = Field(default=None)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    total_tokens_in: int = Field(default=0, ge=0)
    total_tokens_out: int = Field(default=0, ge=0)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = Field(default=None)

    @property
    def total_retrieval_attempts(self) -> int:
        return sum(len(sq.attempts) for sq in self.subquestions)

    @property
    def grounded_subquestions_count(self) -> int:
        return sum(1 for sq in self.subquestions if sq.grounded)
