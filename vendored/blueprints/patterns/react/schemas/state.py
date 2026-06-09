"""Canonical Pydantic v2 state schema for the ReAct pattern.

Recipes that target ReAct (e.g. ``agent-deployments/docs/recipes/research-assistant.md``)
reference these names so frameworks can ground tool dispatch and termination
checks against a shared shape. Self-contained — no cross-pattern imports.

See ``../design.md`` for the prose definition of each field.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """One tool invocation request the agent emits during a step."""

    tool: str = Field(description="Registered tool name the agent asks to invoke.")
    args: dict[str, object] = Field(
        default_factory=dict,
        description="Tool arguments; shape is per-tool and not validated here.",
    )


class Observation(BaseModel):
    """The result of executing a tool call."""

    tool: str = Field(description="The tool that produced this observation.")
    output: str = Field(description="Stringified tool result fed back to the LLM.")
    error: str | None = Field(
        default=None,
        description="Set if the tool raised; output is then the error summary.",
    )


class ReActStep(BaseModel):
    """One think → act → observe iteration."""

    thought: str = Field(description="LLM reasoning for this step.")
    action: ToolCall | None = Field(
        default=None,
        description="Tool the agent chose to call; None when the step is the final answer.",
    )
    observation: Observation | None = Field(
        default=None,
        description="Tool result; None when the step ends the loop without acting.",
    )


class ReActState(BaseModel):
    """Top-level state passed through the ReAct loop."""

    question: str = Field(description="User-supplied task driving the loop.")
    steps: list[ReActStep] = Field(default_factory=list)
    final_answer: str | None = Field(
        default=None,
        description="Set when the agent terminates with a user-visible answer.",
    )
    max_steps: int = Field(default=8, ge=1, description="Hard cap on loop iterations.")
    terminated_reason: str | None = Field(
        default=None,
        description="Why the loop ended: 'answer' | 'max_steps' | 'error'.",
    )
