"""Compact-error retry — bounded retry that feeds a compacted error back.

When a tool call raises, this wrapper catches the failure, compacts it to a
short model-readable summary, and retries up to a fixed budget — then returns a
ToolResult carrying the compacted error so the agent self-corrects or reports
cleanly instead of crashing or spinning.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .schemas import ToolCall, ToolResult

_MAX_ERROR_CHARS = 280


def compact_error(exc: Exception) -> str:
    """Reduce an exception to a short, model-readable one-liner."""
    summary = f"{type(exc).__name__}: {exc}".replace("\n", " ").strip()
    if len(summary) > _MAX_ERROR_CHARS:
        summary = summary[: _MAX_ERROR_CHARS - 1] + "…"
    return summary


@dataclass
class RetryReport:
    """Outcome of a guarded tool execution."""

    result: ToolResult
    attempts: int
    errors: list[str]


def run_with_retry(
    call: ToolCall,
    execute: Callable[[ToolCall], str],
    *,
    max_attempts: int = 3,
) -> RetryReport:
    """Run ``execute(call)``, retrying on exception with a compacted error.

    On success the ToolResult carries the tool output; after ``max_attempts``
    failures it carries the last compacted error (with ``error`` set), so the
    caller injects a clean failure into the conversation instead of raising.
    """
    errors: list[str] = []
    for attempt in range(1, max_attempts + 1):
        try:
            output = execute(call)
        except Exception as exc:
            errors.append(compact_error(exc))
            continue
        return RetryReport(
            result=ToolResult(tool=call.tool, output=output, id=call.id),
            attempts=attempt,
            errors=errors,
        )
    last_error = errors[-1] if errors else "unknown error"
    return RetryReport(
        result=ToolResult(tool=call.tool, output=last_error, error=last_error, id=call.id),
        attempts=max_attempts,
        errors=errors,
    )
