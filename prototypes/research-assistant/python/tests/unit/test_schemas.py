"""Unit tests for schemas."""

from app.models.schemas import ResearchRequest, ResearchStep, Source


def test_research_request():
    req = ResearchRequest(question="What is AI?")
    assert req.question == "What is AI?"
    assert req.max_steps == 5


def test_research_request_custom_steps():
    req = ResearchRequest(question="Test", max_steps=10)
    assert req.max_steps == 10


def test_source():
    source = Source(title="Test", url="https://example.com", excerpt="An excerpt")
    assert source.title == "Test"
    assert source.url == "https://example.com"


def test_research_step():
    step = ResearchStep(step=1, action="search", content="Searching...")
    assert step.action == "search"
    assert step.step == 1
