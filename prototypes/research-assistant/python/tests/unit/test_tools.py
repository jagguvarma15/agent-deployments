"""Unit tests for research tools."""

import pytest

from app.tools.cite_sources import cite_sources
from app.tools.extract_facts import extract_facts
from app.tools.summarize import summarize
from app.tools.web_search import web_search


@pytest.mark.asyncio
async def test_web_search_returns_results():
    result = await web_search("machine learning")
    assert "Machine Learning" in result or "machine" in result.lower()


@pytest.mark.asyncio
async def test_summarize_truncates():
    long_text = "This is a long text. " * 50
    result = await summarize(long_text, max_length=100)
    assert len(result) <= 103  # 100 + "..."
    assert result.endswith("...")


@pytest.mark.asyncio
async def test_summarize_short_text():
    result = await summarize("Short text.")
    assert result == "Short text."


def test_extract_facts_returns_list():
    facts = extract_facts("some text about AI")
    assert isinstance(facts, list)
    assert len(facts) > 0


def test_cite_sources_formats():
    facts = ["Fact one.", "Fact two."]
    result = cite_sources(facts)
    assert "[1]" in result
    assert "[2]" in result


def test_cite_sources_empty():
    result = cite_sources([])
    assert "No facts" in result
