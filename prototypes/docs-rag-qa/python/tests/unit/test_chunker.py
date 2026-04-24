"""Unit tests for document chunker."""

from app.tools.chunker import chunk_document


def test_basic_splitting():
    """Test that a long document is split into multiple chunks."""
    content = ". ".join([f"Sentence number {i} with some extra words to fill space" for i in range(50)]) + "."
    chunks = chunk_document(content, chunk_size=200, overlap=30)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) > 0


def test_overlap_between_chunks():
    """Test that consecutive chunks have overlapping content."""
    content = ". ".join([f"Sentence {i} contains unique word alpha{i}" for i in range(30)]) + "."
    chunks = chunk_document(content, chunk_size=150, overlap=40)
    assert len(chunks) >= 2
    # Verify overlap exists: tail of chunk N should appear in chunk N+1
    for i in range(len(chunks) - 1):
        tail = chunks[i][-40:]
        assert any(word in chunks[i + 1] for word in tail.split() if len(word) > 3)


def test_empty_input():
    """Test that empty or whitespace input returns empty list."""
    assert chunk_document("") == []
    assert chunk_document("   ") == []
    assert chunk_document("\n\t") == []


def test_small_input():
    """Test that input smaller than chunk_size returns a single chunk."""
    content = "This is a short document."
    chunks = chunk_document(content, chunk_size=500, overlap=50)
    assert len(chunks) == 1
    assert chunks[0] == content
