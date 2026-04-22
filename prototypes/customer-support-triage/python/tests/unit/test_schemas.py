"""Unit tests for schemas."""

from app.models.schemas import ClassificationResult, Intent, TriageRequest


def test_classification_result():
    result = ClassificationResult(
        intent=Intent.BILLING,
        confidence=0.95,
        reasoning="Customer mentions billing",
    )
    assert result.intent == Intent.BILLING
    assert result.confidence == 0.95


def test_triage_request():
    req = TriageRequest(message="Help me", user_id="user-1")
    assert req.message == "Help me"
    assert req.user_id == "user-1"


def test_intent_values():
    assert Intent.BILLING.value == "billing"
    assert Intent.TECHNICAL.value == "technical"
    assert Intent.ACCOUNT.value == "account"
    assert Intent.GENERAL.value == "general"
