"""Shared pytest fixtures and test utilities for agent-deployments prototypes."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock


def mock_llm_response(content: str = "Hello from mock LLM", **kwargs: Any) -> MagicMock:
    """Create a mock LLM response object.

    Returns a mock that mimics common LLM response shapes
    (works with litellm, langchain, etc.).

    Usage in tests:
        from testing import mock_llm_response

        mock = mock_llm_response("The answer is 42")
        assert mock.choices[0].message.content == "The answer is 42"
    """
    message = MagicMock()
    message.content = content
    message.role = "assistant"
    message.tool_calls = kwargs.get("tool_calls", [])

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = kwargs.get("finish_reason", "stop")

    response = MagicMock()
    response.choices = [choice]
    response.model = kwargs.get("model", "mock-model")
    response.usage = MagicMock(
        prompt_tokens=kwargs.get("prompt_tokens", 10),
        completion_tokens=kwargs.get("completion_tokens", 20),
        total_tokens=kwargs.get("total_tokens", 30),
    )

    return response


def mock_llm_client(responses: list[str] | None = None) -> AsyncMock:
    """Create a mock async LLM client that returns predefined responses.

    Args:
        responses: List of response strings. Cycles through them on repeated calls.

    Usage in tests:
        client = mock_llm_client(["Answer 1", "Answer 2"])
        result = await client.chat.completions.create(...)
    """
    _responses = responses or ["Mock response"]
    _call_count = 0

    async def _create(**kwargs: Any) -> MagicMock:
        nonlocal _call_count
        content = _responses[_call_count % len(_responses)]
        _call_count += 1
        return mock_llm_response(content, **kwargs)

    client = AsyncMock()
    client.chat.completions.create = _create
    return client
