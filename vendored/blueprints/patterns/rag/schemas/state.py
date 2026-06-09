"""Canonical Pydantic v2 state schema for the RAG pattern.

A ``Query`` is embedded, retrieved against a vector store as a list of
``RetrievedDoc``s, then synthesized into an ``Answer``. Recipes
(``docs-rag-qa.md``) reference these names so the embedder / retriever /
answer-synthesis roles agree on shape. Self-contained — no cross-pattern
imports.

See ``../design.md`` for the prose definition of each field.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Query(BaseModel):
    """The user question + any retrieval-time filters."""

    text: str = Field(description="Natural-language question.")
    filters: dict[str, object] = Field(
        default_factory=dict,
        description="Optional metadata filters passed to the vector store.",
    )
    top_k: int = Field(default=5, ge=1)


class RetrievedDoc(BaseModel):
    """One document chunk pulled from the vector store."""

    id: str = Field(description="Stable doc id; used for citations and deduplication.")
    content: str = Field(description="The chunk text fed into the synthesis prompt.")
    score: float = Field(
        ge=0,
        description="Similarity score (provider-specific; typically cosine).",
    )
    source: str | None = Field(
        default=None,
        description="Origin (filename, URL, or page) for citation formatting.",
    )
    metadata: dict[str, object] = Field(default_factory=dict)


class Answer(BaseModel):
    """The synthesized response with citations."""

    text: str
    citations: list[str] = Field(
        default_factory=list,
        description="RetrievedDoc.id values the answer drew from.",
    )
    grounded: bool = Field(
        default=True,
        description="False if the synthesizer judged the retrieval insufficient.",
    )


class RagState(BaseModel):
    """Top-level state for one RAG turn."""

    query: Query
    retrieved: list[RetrievedDoc] = Field(default_factory=list)
    answer: Answer | None = Field(default=None)
