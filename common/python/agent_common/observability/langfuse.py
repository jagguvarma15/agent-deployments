"""Langfuse client singleton and trace decorator."""

import asyncio
import functools
from typing import Any, Callable

from langfuse import Langfuse

_client: Langfuse | None = None


def get_langfuse(
    *,
    public_key: str | None = None,
    secret_key: str | None = None,
    host: str = "http://localhost:3000",
) -> Langfuse:
    """Get or create the Langfuse singleton client."""
    global _client
    if _client is None:
        _client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
    return _client


def traced(
    name: str | None = None,
    *,
    metadata: dict[str, Any] | None = None,
) -> Callable:
    """Decorator that wraps a function in a Langfuse trace span."""

    def decorator(fn: Callable) -> Callable:
        span_name = name or fn.__name__

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            client = get_langfuse()
            trace = client.trace(name=span_name, metadata=metadata or {})
            span = trace.span(name=span_name)
            try:
                result = await fn(*args, **kwargs)
                span.end(output=str(result)[:500])
                return result
            except Exception as exc:
                span.end(level="ERROR", status_message=str(exc))
                raise

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            client = get_langfuse()
            trace = client.trace(name=span_name, metadata=metadata or {})
            span = trace.span(name=span_name)
            try:
                result = fn(*args, **kwargs)
                span.end(output=str(result)[:500])
                return result
            except Exception as exc:
                span.end(level="ERROR", status_message=str(exc))
                raise

        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper

    return decorator
