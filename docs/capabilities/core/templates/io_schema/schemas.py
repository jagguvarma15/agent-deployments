"""Request/response models for the canonical /chat contract.

The frontend posts ``{"message": "...", "history": [...]}`` and expects
``{"reply": "..."}``. These Pydantic models validate that boundary; extend
them with extra fields (conversation id, metadata, streaming flags) as your
agent grows.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    """One prior turn, oldest first, as sent by the frontend."""

    role: Literal["user", "agent"]
    text: str


class ChatRequest(BaseModel):
    """A chat turn from the frontend."""

    message: str = Field(min_length=1, description="The user's message.")
    history: list[ChatTurn] = Field(
        default_factory=list,
        description="Prior turns, oldest first. May be empty; trim to the context budget before the model call.",
    )


class ChatResponse(BaseModel):
    """The agent's reply to a ChatRequest."""

    reply: str = Field(description="The agent's reply, rendered to the user.")
