"""Unit tests for tool implementations."""

import pytest

from app.tools.stripe import stripe_lookup
from app.tools.kb import _mock_search


@pytest.mark.asyncio
async def test_stripe_lookup_charge():
    result = await stripe_lookup("check charge history")
    assert "charge" in result.lower() or "$49.00" in result


@pytest.mark.asyncio
async def test_stripe_lookup_subscription():
    result = await stripe_lookup("current subscription details")
    assert "subscription" in result.lower() or "Pro" in result


@pytest.mark.asyncio
async def test_stripe_lookup_default():
    result = await stripe_lookup("general info")
    assert "cus_demo123" in result


def test_kb_mock_search_finds_relevant():
    result = _mock_search("reset password", top_k=2)
    assert "password" in result.lower()


def test_kb_mock_search_no_results():
    result = _mock_search("xyzzy foobar baz", top_k=2)
    assert "No relevant articles" in result


def test_kb_mock_search_technical():
    result = _mock_search("API rate limit error", top_k=2)
    assert "rate limit" in result.lower() or "429" in result
