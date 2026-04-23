"""Tests for agent_common.auth module."""

import pytest

from agent_common.auth.jwt import create_token, verify_token

SECRET = "test-secret-key-for-unit-tests"


def test_create_and_verify_token():
    token = create_token("user-123", SECRET)
    payload = verify_token(token, SECRET)
    assert payload.sub == "user-123"


def test_token_with_extra_claims():
    token = create_token("user-456", SECRET, extra={"role": "admin"})
    payload = verify_token(token, SECRET)
    assert payload.sub == "user-456"
    assert payload.extra["role"] == "admin"


def test_invalid_token_raises():
    with pytest.raises(ValueError, match="Invalid token"):
        verify_token("not-a-real-token", SECRET)


def test_wrong_secret_raises():
    token = create_token("user-789", SECRET)
    with pytest.raises(ValueError, match="Invalid token"):
        verify_token(token, "wrong-secret")
