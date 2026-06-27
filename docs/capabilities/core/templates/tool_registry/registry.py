"""Typed tool registry — schema export + permission-gated, retry-wrapped dispatch.

Register your domain tools here (see README.md). The registry exposes
OpenAI-compatible JSON schemas for the model and routes each ToolCall through the
permission gate and the compact-error retry wrapper before returning a
ToolResult. The scaffold emits this framework; you implement the tool functions.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .permissions import ApprovalPrompt, Permission, PermissionDecision, PermissionGate
from .retry import run_with_retry
from .schemas import ToolCall, ToolResult


@dataclass
class Tool:
    """A callable tool: a name, a description, a JSON-Schema for its args, the fn."""

    name: str
    description: str
    parameters: dict[str, Any]
    fn: Callable[..., Any]
    permission: Permission = Permission.ASK

    def to_schema(self) -> dict[str, Any]:
        """OpenAI-compatible tool schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def run(self, args: dict[str, Any]) -> str:
        result = self.fn(**args)
        return result if isinstance(result, str) else json.dumps(result)


class ToolRegistry:
    """Holds the registered tools and dispatches calls through the gate + retry."""

    def __init__(self, *, approve: ApprovalPrompt | None = None, max_attempts: int = 3) -> None:
        self._tools: dict[str, Tool] = {}
        self._approve = approve
        self._max_attempts = max_attempts

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict[str, Any]]:
        """The tool list to hand the model."""
        return [tool.to_schema() for tool in self._tools.values()]

    def dispatch(self, call: ToolCall) -> ToolResult:
        """Gate, then execute (with retry), the requested tool call."""
        tool = self._tools.get(call.tool)
        if tool is None:
            return ToolResult(
                tool=call.tool, output=f"unknown tool: {call.tool}", error="unknown tool", id=call.id
            )
        gate = PermissionGate(
            {name: t.permission for name, t in self._tools.items()}, approve=self._approve
        )
        decision: PermissionDecision = gate.check(call)
        if not decision.allowed:
            return ToolResult(
                tool=call.tool, output=decision.reason, error="permission denied", id=call.id
            )
        report = run_with_retry(call, lambda c: tool.run(c.args), max_attempts=self._max_attempts)
        return report.result
