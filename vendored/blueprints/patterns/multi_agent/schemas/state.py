"""Canonical Pydantic v2 state schema for the Multi-Agent pattern.

A supervisor (or peer-coordinator) dispatches sub-tasks to worker agents;
each worker emits an ``AgentResult``; the supervisor synthesizes a final
answer. Covers both flat and hierarchical multi-agent topologies. Recipes
(``ops-crew.md``, ``hierarchical-agent.md``, ``restaurant-rebooking.md``)
reference these names. Self-contained — no cross-pattern imports.

See ``../design.md`` for the prose definition of each field.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    """One worker agent's response to a delegated sub-task."""

    agent_name: str = Field(description="Stable id of the worker (e.g. 'researcher').")
    task: str = Field(description="The sub-task the supervisor handed to this worker.")
    output: str = Field(description="The worker's free-form answer.")
    success: bool = True
    error: str | None = None
    metadata: dict[str, object] = Field(
        default_factory=dict,
        description="Worker-specific extras (token counts, cited sources, etc.).",
    )


class SupervisorDecision(BaseModel):
    """The supervisor's routing / termination decision for one round."""

    next_agent: str | None = Field(
        default=None,
        description="Worker name to dispatch to; None means terminate.",
    )
    task: str | None = Field(
        default=None,
        description="Sub-task to hand to the chosen worker; None when terminating.",
    )
    reasoning: str | None = None
    terminate: bool = False


class MultiAgentState(BaseModel):
    """Top-level state for a multi-agent run."""

    user_goal: str
    decisions: list[SupervisorDecision] = Field(default_factory=list)
    agent_results: list[AgentResult] = Field(default_factory=list)
    final_answer: str | None = Field(default=None)
    rounds: int = Field(default=0, ge=0, description="Supervisor invocations so far.")
    max_rounds: int = Field(default=10, ge=1, description="Hard cap on supervisor cycles.")
