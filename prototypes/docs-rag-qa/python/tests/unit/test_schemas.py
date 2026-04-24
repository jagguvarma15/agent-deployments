"""Unit tests for schemas."""

from app.models.schemas import Citation, DocumentIngestRequest, QueryRequest


def test_document_ingest_request():
    req = DocumentIngestRequest(content="Hello world", title="Test Doc")
    assert req.content == "Hello world"
    assert req.title == "Test Doc"
    assert req.metadata is None


def test_query_request_defaults():
    req = QueryRequest(question="What is Python?")
    assert req.question == "What is Python?"
    assert req.top_k == 5


def test_citation_model():
    citation = Citation(
        chunk_id="chunk-1",
        document_title="Guide",
        text="Some relevant text",
        score=0.95,
    )
    assert citation.chunk_id == "chunk-1"
    assert citation.score == 0.95
