"""Tool permissions — Always / Ask / Never gating for tool execution.

Each registered tool carries a permission tier. The gate consults it before any
tool runs: ALWAYS executes silently, ASK routes to a human-approval callback
(the human-in-the-loop seam), and NEVER refuses outright. Unclassified tools
default to ASK: fail safe, never silently run.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .schemas import ToolCall


class Permission(str, Enum):
    """How a tool may be invoked."""

    ALWAYS = "always"  # run without asking
    ASK = "ask"  # require human approval first
    NEVER = "never"  # refuse outright


@dataclass
class PermissionDecision:
    """The outcome of gating one tool call."""

    allowed: bool
    permission: Permission
    reason: str = ""


class ApprovalPrompt(Protocol):
    """Asks a human to approve one ASK-tier tool call; returns True to allow."""

    def __call__(self, call: ToolCall, reason: str) -> bool: ...


class PermissionGate:
    """Maps tool name -> Permission and decides whether a call may run.

    A tool absent from the map falls back to ``default`` (ASK) — a tool nobody
    classified is treated as needing approval, never silently allowed.
    """

    def __init__(
        self,
        permissions: dict[str, Permission],
        *,
        approve: ApprovalPrompt | None = None,
        default: Permission = Permission.ASK,
    ) -> None:
        self._permissions = dict(permissions)
        self._approve = approve
        self._default = default

    def permission_for(self, tool: str) -> Permission:
        return self._permissions.get(tool, self._default)

    def check(self, call: ToolCall) -> PermissionDecision:
        permission = self.permission_for(call.tool)
        if permission is Permission.ALWAYS:
            return PermissionDecision(True, permission, "allowed (ALWAYS)")
        if permission is Permission.NEVER:
            return PermissionDecision(False, permission, f"tool {call.tool!r} denied (NEVER)")
        reason = f"tool {call.tool!r} requires approval"
        if self._approve is None:
            return PermissionDecision(False, permission, f"{reason} but no approver configured")
        approved = self._approve(call, reason)
        verdict = "approved" if approved else "declined"
        return PermissionDecision(approved, permission, f"{reason} — {verdict}")
