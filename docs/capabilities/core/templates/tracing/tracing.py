"""Structured tracing — one JSON line per span around model and tool calls.

The T3 production substrate: every model call and tool invocation is bracketed
by a span that records what ran, how long it took, and what it cost (token
counts), without forcing a backend choice. Spans land as JSONL at
``TRACE_PATH`` (default ``.agent/trace.jsonl``; the sentinel value ``stdout``
prints them instead). Observability backends (obs.langfuse / obs.langsmith /
obs.grafana-stack) are exporters layered on top of this stream — they consume
what the tracer emits; the tracer never depends on them.

Every string attribute passes through :func:`_redact` first, so a stray secret
in a span payload never lands on disk. Self-contained: standard library only.

Wiring::

    from agent.tracing import model_call, span

    with span("retrieve", query_id=qid):
        docs = store.search(query)

    with model_call("claude-opus-4-8") as call:
        response = client.messages.create(...)
        call["input_tokens"] = response.usage.input_tokens
        call["output_tokens"] = response.usage.output_tokens

Disable with ``TRACE_ENABLED=0`` (spans become no-ops; the file is untouched).
The ``.agent/trace.jsonl`` stream is runtime output — gitignore it, like
``.agent/runs/`` (the scaffold does this by default).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TRACE_PATH = ".agent/trace.jsonl"
STDOUT_SENTINEL = "stdout"

# ── Redaction ──────────────────────────────────────────────────────────────────
# Conservative secret-shaped patterns: a false positive on legit text is far
# cheaper than a single leaked credential. Prefix is preserved so the reader can
# see *which* kind of secret was redacted without seeing its value. Kept in
# sync with agent/steplog.py (the T2 sibling substrate).
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
    return datetime.now(timezone.utc).isoformat()


def _enabled() -> bool:
    return os.environ.get("TRACE_ENABLED", "1").strip().lower() not in ("0", "false", "no")


def _emit(event: dict[str, Any]) -> None:
    """Append one redacted JSON line to the configured sink. Never raises."""
    line = json.dumps(_redact_obj(event), ensure_ascii=False, default=str)
    target = os.environ.get("TRACE_PATH", DEFAULT_TRACE_PATH).strip() or DEFAULT_TRACE_PATH
    try:
        if target == STDOUT_SENTINEL:
            print(line, file=sys.stdout, flush=True)
            return
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as sink:
            sink.write(line + "\n")
    except OSError:
        # Tracing must never take the agent down; a full disk or read-only
        # mount silently drops the span.
        pass


@contextmanager
def span(name: str, **attrs: Any) -> Iterator[dict[str, Any]]:
    """Bracket a unit of work with one trace span.

    Yields a mutable dict the caller may enrich mid-span (token counts, result
    sizes); everything in it lands in the event's ``attrs``. An exception marks
    the span ``error`` (with the exception type) and re-raises.
    """
    if not _enabled():
        yield {}
        return
    enriched: dict[str, Any] = dict(attrs)
    started = time.monotonic()
    ts = _utc_now_iso()
    status = "ok"
    try:
        yield enriched
    except BaseException as exc:
        status = "error"
        enriched.setdefault("error", type(exc).__name__)
        raise
    finally:
        _emit(
            {
                "ts": ts,
                "span": name,
                "status": status,
                "duration_ms": round((time.monotonic() - started) * 1000, 3),
                "attrs": enriched,
            }
        )


@contextmanager
def model_call(model: str, **attrs: Any) -> Iterator[dict[str, Any]]:
    """The canonical model-call span: set token counts on the yielded dict.

    ``with model_call("claude-opus-4-8") as call:`` then assign
    ``call["input_tokens"]`` / ``call["output_tokens"]`` from the response
    usage so cost attribution survives in the trace.
    """
    with span("model_call", model=model, **attrs) as call:
        yield call
