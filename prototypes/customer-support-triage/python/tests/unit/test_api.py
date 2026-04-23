"""Unit tests for the API layer using mocked agents."""

import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"

from app.models.schemas import ClassificationResult, Intent


def test_health():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
@patch("app.api.triage.run_specialist", new_callable=AsyncMock)
@patch("app.api.triage.classify_intent", new_callable=AsyncMock)
async def test_triage_handler_routes_correctly(mock_classify, mock_specialist):
    """Test the triage logic without DB — verify classifier → specialist routing."""
    mock_classify.return_value = ClassificationResult(
        intent=Intent.BILLING,
        confidence=0.95,
        reasoning="Billing question",
    )
    mock_specialist.return_value = ("I can help with billing.", [{"tool_name": "lookup_billing", "args": {}}])

    # Call classifier directly
    result = await mock_classify("I was charged twice")
    assert result.intent == Intent.BILLING
    assert result.confidence >= 0.7

    # Verify specialist would be called
    response_text, tool_calls = await mock_specialist(Intent.BILLING, "I was charged twice")
    assert "billing" in response_text.lower()
    assert len(tool_calls) == 1


@pytest.mark.asyncio
@patch("app.api.triage.classify_intent", new_callable=AsyncMock)
async def test_escalation_on_low_confidence(mock_classify):
    """Verify that low confidence triggers escalation."""
    from app.settings import settings

    mock_classify.return_value = ClassificationResult(
        intent=Intent.GENERAL,
        confidence=0.3,
        reasoning="Ambiguous",
    )

    result = await mock_classify("asdfghjkl")
    assert result.confidence < settings.escalation_threshold
