"""Serializable step-log — the agent's run state as an append-only jsonl log.

Each run gets its own directory under ``.agent/runs/<run_id>/`` holding an
``events.jsonl`` sink: one JSON object per line (``{"ts", "kind", "payload"}``).
The log *is* the state — replaying the events reconstructs where a run got to,
so a multi-step agent can pause, resume, retry a failed step, or be traced after
the fact without a database.

Every string written passes through :func:`_redact` first, so a stray secret in
a step payload never lands on disk. Self-contained: standard library only.

Wiring::

    from agent.steplog import StepLog, StepStatus

    with StepLog() as log:                 # writes .agent/runs/<id>/events.jsonl
        step = log.start("fetch")
        try:
            ...                            # do the work
            log.finish(step, StepStatus.DONE)
        except Exception as exc:
            log.finish(step, StepStatus.FAILED, error=str(exc))

On the next run, ``replay_states(log.events_path)`` folds the events back into
per-step states — a step left RUNNING (crash mid-step) comes back PENDING, so a
resume re-runs it.
"""

from __future__ import annotations

import json
import re
import secrets
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

RUNS_ROOT = Path(".agent/runs")
EVENTS_FILENAME = "events.jsonl"


class StepStatus(str, Enum):
    """Lifecycle of one step.

    A step left ``RUNNING`` (the process died before a terminal event) is
    reported ``PENDING`` on replay, so a resume re-runs it.
    """

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepState:
    """The recorded state of a single step — serializable to/from the jsonl."""

    step_id: str
    status: StepStatus = StepStatus.PENDING
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    attempt: int = 0


# ── Redaction ──────────────────────────────────────────────────────────────────
# Conservative secret-shaped patterns: a false positive on legit text is far
# cheaper than a single leaked credential. Prefix is preserved so the reader can
# see *which* kind of secret was redacted without seeing its value.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"), "sk-ant-...REDACTED"),
    (re.compile(r"sk-(?!ant-)[A-Za-z0-9_\-]{20,}"), "sk-...REDACTED"),
    (re.compile(r"[Bb]earer\s+[A-Za-z0-9._\-]+"), "Bearer REDACTED"),
    (
        re.compile(r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.\-]*://[^:/?#@]*):[^@/?#\s]+@"),
        r"\g<scheme>:REDACTED@",
    ),
    (re.compile(r"github_pat_[A-Za-z0-9_]{30,}"), "github_pat_REDACTED"),
)


def _redact(text: str) -> str:
    """Return ``text`` with every known secret-shaped substring replaced."""
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _redact_obj(obj: Any) -> Any:
    """Recursively redact strings inside dicts / lists / tuples."""
    if isinstance(obj, str):
        return _redact(obj)
    if isinstance(obj, Mapping):
        return {k: _redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_redact_obj(v) for v in obj]
    return obj


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# ── Sink ────────────────────────────────────────────────────────────────────────
class StepLog:
    """A run-scoped append-only event sink. Use as a context manager.

    Opens ``.agent/runs/<run_id>/events.jsonl`` line-buffered, so a crash
    mid-run still leaves a readable tail. ``close`` is idempotent.
    """

    def __init__(self, root: Path | str = RUNS_ROOT) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.run_id = f"{stamp}-{secrets.token_hex(3)}"
        self.run_dir = Path(root) / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.run_dir / EVENTS_FILENAME
        self._events = self.events_path.open("a", buffering=1, encoding="utf-8")
        self._closed = False
        self.record("run_started", {"run_id": self.run_id})

    def record(self, kind: str, payload: Any = None) -> None:
        """Append one ``{ts, kind, payload}`` line, secrets redacted."""
        if self._closed:
            return
        line = json.dumps(
            {"ts": _utc_now_iso(), "kind": kind, "payload": _redact_obj(payload)},
            default=str,
        )
        self._events.write(line + "\n")

    def start(self, step_id: str, *, attempt: int = 1) -> StepState:
        """Mark ``step_id`` RUNNING and record it; returns its StepState."""
        state = StepState(
            step_id=step_id,
            status=StepStatus.RUNNING,
            started_at=_utc_now_iso(),
            attempt=attempt,
        )
        self.record("step_started", {"step_id": step_id, "attempt": attempt})
        return state

    def finish(
        self, step: StepState, status: StepStatus, *, error: str | None = None
    ) -> StepState:
        """Mark ``step`` terminal (DONE / FAILED / SKIPPED) and record it."""
        step.status = status
        step.completed_at = _utc_now_iso()
        step.error = error
        self.record(
            "step_finished",
            {"step_id": step.step_id, "status": status.value, "error": error},
        )
        return step

    def close(self, status: str = "completed") -> None:
        if self._closed:
            return
        self.record("run_finished", {"status": status})
        self._closed = True
        self._events.close()

    def __enter__(self) -> StepLog:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close(status="failed" if exc_type is not None else "completed")


# ── Replay (the resume primitive) ───────────────────────────────────────────────
def read_events(events_path: Path | str) -> Iterator[dict[str, Any]]:
    """Yield each recorded event dict from a run's ``events.jsonl``."""
    with Path(events_path).open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if line:
                yield json.loads(line)


def replay_states(events_path: Path | str) -> dict[str, StepState]:
    """Fold a run's events back into per-step :class:`StepState`s.

    A step left RUNNING (the process died mid-step) comes back PENDING so a
    resume re-runs it. This is the pause / resume / retry substrate: the jsonl
    is the durable state, and this reconstructs it in memory.
    """
    states: dict[str, StepState] = {}
    for event in read_events(events_path):
        kind = event.get("kind")
        payload = event.get("payload") or {}
        step_id = payload.get("step_id")
        if not step_id:
            continue
        if kind == "step_started":
            states[step_id] = StepState(
                step_id=step_id,
                status=StepStatus.RUNNING,
                started_at=event.get("ts"),
                attempt=payload.get("attempt", 1),
            )
        elif kind == "step_finished" and step_id in states:
            state = states[step_id]
            state.status = StepStatus(payload.get("status", "failed"))
            state.completed_at = event.get("ts")
            state.error = payload.get("error")
    for state in states.values():
        if state.status is StepStatus.RUNNING:
            state.status = StepStatus.PENDING
    return states


__all__ = [
    "StepStatus",
    "StepState",
    "StepLog",
    "read_events",
    "replay_states",
]
