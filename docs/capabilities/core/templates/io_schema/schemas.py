"""Request/response models for the canonical /chat contract.

The frontend posts ``{"message": "..."}`` and expects ``{"reply": "..."}``.
These Pydantic models validate that boundary; extend them with extra fields
(conversation id, metadata, streaming flags) as your agent grows.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """A chat turn from the frontend."""

    message: str = Field(min_length=1, description="The user's message.")


class ChatResponse(BaseModel):
    """The agent's reply to a ChatRequest."""

    reply: str = Field(description="The agent's reply, rendered to the user.")
