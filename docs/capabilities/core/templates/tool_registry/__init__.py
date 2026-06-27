"""Tool subsystem: typed registry, permission tiers, compact-error retry.

The scaffold emits this package (the framework); you implement the domain tools.
See README.md to register one.
"""

from .permissions import ApprovalPrompt, Permission, PermissionDecision, PermissionGate
from .registry import Tool, ToolRegistry
from .retry import RetryReport, compact_error, run_with_retry
from .schemas import ToolCall, ToolResult

__all__ = [
    "ApprovalPrompt",
    "Permission",
    "PermissionDecision",
    "PermissionGate",
    "RetryReport",
    "Tool",
    "ToolCall",
    "ToolRegistry",
    "ToolResult",
    "compact_error",
    "run_with_retry",
]
