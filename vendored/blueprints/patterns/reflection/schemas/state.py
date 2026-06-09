"""Canonical Pydantic v2 state schema for the Reflection pattern.

A drafter LLM produces a ``Draft``; a critic LLM evaluates it and emits a
``Critique`` with revision guidance. The loop iterates until the critic
accepts or ``max_iterations`` is hit. Self-contained — no cross-pattern
imports.

See ``../design.md`` for the prose definition of each field.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Draft(BaseModel):
    """One draft attempt at the goal."""

    iteration: int = Field(ge=0, description="0-indexed draft number.")
    content: str = Field(description="The draft itself; format is task-specific.")
    notes: str | None = Field(
        default=None,
        description="Drafter's own commentary on choices made this iteration.",
    )


class Critique(BaseModel):
    """The critic's response to a Draft."""

    iteration: int = Field(ge=0, description="Matches the Draft.iteration it critiques.")
    accepted: bool = Field(description="True ends the reflection loop.")
    score: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Optional 0..1 quality score for routing / analytics.",
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Concrete problems the critic found; drafter must address each.",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Critic-proposed fixes; drafter may follow or rewrite.",
    )


class ReflectionState(BaseModel):
    """Top-level state for a Reflection loop."""

    goal: str
    drafts: list[Draft] = Field(default_factory=list)
    critiques: list[Critique] = Field(default_factory=list)
    final_answer: str | None = Field(default=None)
    max_iterations: int = Field(default=3, ge=1)
    terminated_reason: str | None = Field(
        default=None,
        description="'accepted' | 'max_iterations' | 'error'.",
    )
