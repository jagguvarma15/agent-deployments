"""Canonical Pydantic v2 state schema for the Human-in-the-Loop pattern.

An agent loop pauses at an ``Interrupt`` and waits for ``HumanInput``
before continuing. Common uses: approval gates, clarifying questions,
high-stakes action confirmations. Self-contained — no cross-pattern
imports.

See ``../design.md`` for the prose definition of each field.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

InterruptKind = Literal["approval", "clarification", "selection", "input"]


class Interrupt(BaseModel):
    """A pause point in the agent loop that needs human input."""

    id: str = Field(description="Stable id used to correlate the matching HumanInput.")
    kind: InterruptKind = Field(description="What kind of response the agent expects.")
    prompt: str = Field(description="What to show the human.")
    options: list[str] = Field(
        default_factory=list,
        description="Choices for 'approval' (yes/no) or 'selection' interrupts; empty for free input.",
    )
    context: dict[str, object] = Field(
        default_factory=dict,
        description="Snapshot of agent state the human needs to decide.",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = Field(
        default=None,
        description="If set, the interrupt auto-fails after this timestamp.",
    )


class HumanInput(BaseModel):
    """The human's response to an Interrupt."""

    interrupt_id: str = Field(description="Matches Interrupt.id.")
    response: str = Field(description="Free-text or one of Interrupt.options.")
    approved: bool | None = Field(
        default=None,
        description="Convenience flag for 'approval' kind; None for other kinds.",
    )
    responder: str | None = Field(
        default=None,
        description="User id of the responder; used for audit.",
    )
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HitlState(BaseModel):
    """Top-level state for a HITL-capable agent loop."""

    goal: str
    pending_interrupt: Interrupt | None = Field(
        default=None,
        description="Set when the loop is waiting; cleared once a HumanInput resolves it.",
    )
    interrupt_history: list[Interrupt] = Field(default_factory=list)
    input_history: list[HumanInput] = Field(default_factory=list)
    final_answer: str | None = Field(default=None)
    terminated_reason: str | None = Field(
        default=None,
        description="'completed' | 'cancelled_by_human' | 'interrupt_expired' | 'error'.",
    )
