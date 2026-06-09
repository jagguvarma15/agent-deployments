"""Canonical Pydantic v2 state schema for the Routing pattern.

A router LLM classifies an incoming request into one of N predeclared
``Route``s; the picked route names the specialist handler (agent, tool,
or workflow) to delegate to. Self-contained — no cross-pattern imports.

See ``../design.md`` for the prose definition of each field.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Route(BaseModel):
    """One available specialist the router can dispatch to."""

    name: str = Field(description="Stable id (e.g. 'billing', 'tech_support').")
    description: str = Field(description="When to pick this route; shown to the router LLM in the prompt.")


class RouteDecision(BaseModel):
    """The router's classification output."""

    route: str = Field(description="Name of the picked Route.")
    confidence: float = Field(
        ge=0,
        le=1,
        description="Router's self-reported certainty; downstream may force a fallback below threshold.",
    )
    reasoning: str | None = Field(
        default=None,
        description="Optional explanation; useful for audit logs.",
    )


class RoutingState(BaseModel):
    """Top-level state for one routing turn."""

    request: str = Field(description="The user request being classified.")
    available_routes: list[Route] = Field(
        min_length=1,
        description="The set the router chooses from.",
    )
    decision: RouteDecision | None = Field(
        default=None,
        description="Set after the router responds; None means routing hasn't run yet.",
    )
    fallback_route: str | None = Field(
        default=None,
        description="Route name used when decision.confidence falls below threshold.",
    )
    handler_output: str | None = Field(
        default=None,
        description="Result of running the selected specialist.",
    )
