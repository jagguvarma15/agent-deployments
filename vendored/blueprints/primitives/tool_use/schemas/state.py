"""Canonical Pydantic v2 state schema for the Tool Use pattern.

Tool Use is the substrate ReAct (and most other agent patterns) build on:
a single LLM turn that requests one or more tool calls and consumes the
results. Recipes targeting Tool Use bind their tool registry against the
``ToolCall`` shape declared here. Self-contained — no cross-pattern
imports.

See ``../design.md`` for the prose definition of each field.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """One tool invocation request from the LLM."""

    tool: str = Field(description="Registered tool name.")
    args: dict[str, object] = Field(default_factory=dict)
    id: str | None = Field(
        default=None,
        description="Provider-supplied id used to correlate the matching ToolResult.",
    )


class ToolResult(BaseModel):
    """The outcome of executing a ToolCall."""

    tool: str
    output: str = Field(description="Stringified tool output returned to the model.")
    error: str | None = Field(
        default=None,
        description="Set when the tool raised; output is then the error summary.",
    )
    id: str | None = Field(
        default=None,
        description="Matches ToolCall.id when the provider supplies one.",
    )


class ToolUseState(BaseModel):
    """Top-level state for a single Tool Use turn."""

    user_message: str = Field(description="The user message that prompted the turn.")
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    final_answer: str | None = Field(default=None)
