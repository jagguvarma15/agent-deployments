"""Intent classifier using Pydantic AI with structured output."""

from pydantic_ai import Agent

from app.models.schemas import ClassificationResult
from app.settings import settings

CLASSIFIER_SYSTEM_PROMPT = """You are a customer support intent classifier.
Given a customer message, classify it into exactly one of these intents:
- billing: payment issues, subscription changes, invoices, charges, refunds
- technical: bugs, errors, API issues, integration problems, performance
- account: password resets, profile updates, access issues, account settings
- general: everything else, general questions, feedback, feature requests

Return the intent, your confidence (0.0 to 1.0), and brief reasoning."""

_classifier_agent: Agent | None = None


def _get_classifier() -> Agent:
    global _classifier_agent
    if _classifier_agent is None:
        _classifier_agent = Agent(
            f"anthropic:{settings.classifier_model}",
            result_type=ClassificationResult,
            system_prompt=CLASSIFIER_SYSTEM_PROMPT,
        )
    return _classifier_agent


async def classify_intent(message: str) -> ClassificationResult:
    """Classify a customer message into an intent category."""
    agent = _get_classifier()
    result = await agent.run(message)
    return result.data
