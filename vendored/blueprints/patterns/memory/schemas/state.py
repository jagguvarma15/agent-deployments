"""Canonical Pydantic v2 state schema for the Memory pattern.

A memory store holds ``MemoryEntry`` records keyed by user + scope; reads
return a ``Recall`` of the most relevant entries for a given turn. Recipes
(``memory-assistant.md``) reference these names so extraction / recall /
chat roles agree on shape. Self-contained — no cross-pattern imports.

See ``../design.md`` for the prose definition of each field.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    """One stored fact or preference about the user."""

    id: str = Field(description="Stable id (typically a UUID).")
    user_id: str = Field(description="Owner of the memory; isolation boundary.")
    content: str = Field(description="Natural-language statement of the memory.")
    kind: str = Field(
        default="fact",
        description="Coarse category (fact | preference | event | constraint).",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_used_at: datetime | None = Field(
        default=None,
        description="Updated when this entry is included in a Recall; drives eviction.",
    )
    metadata: dict[str, object] = Field(default_factory=dict)


class Recall(BaseModel):
    """A ranked set of entries returned for a single retrieval."""

    user_id: str
    query: str = Field(description="What the recall was asked to match against.")
    entries: list[MemoryEntry] = Field(default_factory=list)
    scores: list[float] = Field(
        default_factory=list,
        description="One score per entry (same index); empty if scoring wasn't used.",
    )


class MemoryState(BaseModel):
    """Top-level state for a turn that consults memory."""

    user_id: str
    user_message: str
    recall: Recall | None = Field(
        default=None,
        description="Set after retrieval runs; None for turns that skip memory.",
    )
    new_entries: list[MemoryEntry] = Field(
        default_factory=list,
        description="Memories the extractor produced from this turn (write path).",
    )
    response: str | None = Field(default=None)
