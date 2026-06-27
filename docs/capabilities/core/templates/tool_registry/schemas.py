"""Typed tool-call schemas — the contract between the model and the registry."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """One tool invocation requested by the model."""

    tool: str = Field(description="Registered tool name.")
    args: dict[str, object] = Field(default_factory=dict)
    id: str | None = Field(default=None, description="Provider id correlating the ToolResult.")


class ToolResult(BaseModel):
    """The outcome of executing a ToolCall."""

    tool: str
    output: str = Field(description="Stringified tool output returned to the model.")
    error: str | None = Field(default=None, description="Set when the tool raised.")
    id: str | None = Field(default=None, description="Matches ToolCall.id when supplied.")
