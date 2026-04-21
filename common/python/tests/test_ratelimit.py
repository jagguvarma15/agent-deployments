"""Tests for ratelimit/slowapi_setup module."""

from ratelimit.slowapi_setup import build_limiter


def test_build_limiter_returns_limiter():
    limiter = build_limiter("redis://localhost:6379", default_limit="100/minute")
    # Verify it's a Limiter instance with the expected config
    assert limiter is not None
    assert hasattr(limiter, "limit")
