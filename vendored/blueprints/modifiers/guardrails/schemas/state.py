"""Canonical Pydantic v2 state schema for the Guardrails modifier.

The modifier wraps any pattern with three policy layers (input / tool /
output) plus an optional dual-LLM split. Recipes targeting Guardrails
reference these names so frameworks can ground per-layer verdicts,
block decisions, and audit emission against a shared shape.

Self-contained — no cross-pattern imports.

See ``../design.md`` for the prose definition of each field.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

Layer = Literal["input", "tool", "output"]
VerdictKind = Literal["allow", "flag", "block", "rewrite"]
DetectorCostClass = Literal["cheap", "medium", "expensive"]
FailurePolicy = Literal["fail_open", "fail_closed"]


class Verdict(BaseModel):
    """One detector's decision on one payload."""

    kind: VerdictKind = Field(description="What the detector decided.")
    detector: str = Field(description="Stable detector name; appears in audit.")
    reason: str | None = Field(
        default=None,
        description="Short explanation; surfaced to audit, never to the end user.",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Detector's self-reported confidence, where applicable.",
    )
    suggestion: str | None = Field(
        default=None,
        description="For 'rewrite' verdicts, the directive the agent should follow on regenerate.",
    )


class LayerResult(BaseModel):
    """One layer's pass over a payload — all detectors that ran and the final outcome."""

    layer: Layer
    verdicts: list[Verdict] = Field(default_factory=list)
    blocked: bool = Field(
        default=False,
        description="True if any detector returned 'block'.",
    )
    rewritten: bool = Field(
        default=False,
        description="True if at least one 'rewrite' verdict fired without a block.",
    )
    duration_ms: int = Field(
        default=0,
        ge=0,
        description="Wall-clock time spent in this layer.",
    )

    @property
    def first_block(self) -> Verdict | None:
        for v in self.verdicts:
            if v.kind == "block":
                return v
        return None


class BlockDecision(BaseModel):
    """One row in the audit sink. Persisted whether or not the layer blocked."""

    request_id: str = Field(description="Correlates all layers for one wrapped-agent call.")
    layer: Layer
    detector: str
    verdict: VerdictKind
    action_taken: Literal["allowed", "blocked", "rewritten", "audited_only"] = Field(
        description="What the gateway actually did, after applying fail-open/closed policy.",
    )
    input_hash: str = Field(
        description="SHA-256 of the payload checked. Never log the payload itself.",
    )
    policy_version: str = Field(description="Version tag of the policy artifact that produced this verdict.")
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class QuarantinedCall(BaseModel):
    """One invocation of the quarantined LLM that read untrusted tool output."""

    tool_name: str = Field(description="The tool whose output was summarized.")
    schema_id: str = Field(description="Identifier of the structured-output schema enforced.")
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    model: str = Field(description="Model id for the quarantined call (typically a small fast model).")
    duration_ms: int = Field(ge=0)


class GuardrailsState(BaseModel):
    """Per-request state the modifier maintains alongside the wrapped agent's state.

    Recipes can consult this state for trace emission, audit replay, and
    after-the-fact false-positive triage.
    """

    request_id: str
    policy_version: str = Field(description="Version of the policy artifact applied to this request.")
    tenant: str | None = Field(default=None, description="Tenant id for per-tenant policy lookup.")
    input_layer: LayerResult | None = Field(default=None)
    tool_layers: list[LayerResult] = Field(
        default_factory=list,
        description="One LayerResult per tool call attempted during the request.",
    )
    output_layer: LayerResult | None = Field(default=None)
    quarantined_calls: list[QuarantinedCall] = Field(
        default_factory=list,
        description="Empty when dual-LLM is disabled OR no untrusted tool output was read.",
    )
    outcome: Literal["allowed", "blocked", "rewritten"] | None = Field(
        default=None,
        description="Final disposition of the request after every layer ran.",
    )
    blocked_at: Layer | None = Field(
        default=None,
        description="Layer that returned the terminal block, if any.",
    )

    @property
    def total_duration_ms(self) -> int:
        layers = [self.input_layer, self.output_layer, *self.tool_layers]
        return sum(layer.duration_ms for layer in layers if layer is not None)
