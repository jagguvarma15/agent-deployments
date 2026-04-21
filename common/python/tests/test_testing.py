"""Tests for agent_common.testing module."""

import pytest

from agent_common.testing import mock_llm_response, mock_llm_client


def test_mock_llm_response_default():
    response = mock_llm_response()
    assert response.choices[0].message.content == "Hello from mock LLM"
    assert response.choices[0].message.role == "assistant"


def test_mock_llm_response_custom():
    response = mock_llm_response("Custom answer", model="gpt-4")
    assert response.choices[0].message.content == "Custom answer"


@pytest.mark.asyncio
async def test_mock_llm_client():
    client = mock_llm_client(["Response 1", "Response 2"])
    r1 = await client.chat.completions.create(model="test")
    assert r1.choices[0].message.content == "Response 1"
    r2 = await client.chat.completions.create(model="test")
    assert r2.choices[0].message.content == "Response 2"
