"""Tests for agent_common.ratelimit module."""

from agent_common.ratelimit import build_limiter


def test_build_limiter_returns_limiter():
    limiter = build_limiter("redis://localhost:6379", default_limit="100/minute")
    assert limiter is not None
    assert hasattr(limiter, "limit")
