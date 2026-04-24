"""Unit tests for the in-memory retriever."""

from app.tools.retriever import _document_store, search_similar, store_chunks


def test_store_and_search():
    """Test storing chunks and searching for them."""
    _document_store.clear()
    store_chunks("doc-1", "Python Guide", ["Python is a programming language.", "Python supports async programming."])
    result = search_similar("Python programming")
    assert "Python" in result
    assert "No relevant documents found" not in result


def test_no_results():
    """Test search with no matching documents."""
    _document_store.clear()
    store_chunks("doc-2", "Cooking Tips", ["Add salt to boiling water.", "Preheat the oven to 350 degrees."])
    result = search_similar("quantum physics entanglement")
    assert "No relevant documents found" in result


def test_top_k_limiting():
    """Test that top_k limits the number of results."""
    _document_store.clear()
    chunks = [f"Document chunk {i} about testing software applications." for i in range(10)]
    store_chunks("doc-3", "Testing Guide", chunks)
    result_k1 = search_similar("testing software", top_k=1)
    result_k5 = search_similar("testing software", top_k=5)
    # With top_k=1, should have fewer separator sections than top_k=5
    assert result_k1.count("---") < result_k5.count("---")
