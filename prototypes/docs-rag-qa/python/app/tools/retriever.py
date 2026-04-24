"""In-memory mock vector store for document retrieval."""

import uuid

_document_store: dict[str, list[dict]] = {}


def store_chunks(document_id: str, title: str, chunks: list[str]) -> None:
    """Store document chunks in the in-memory store.

    Args:
        document_id: Unique identifier for the document.
        title: Title of the document.
        chunks: List of text chunks to store.
    """
    entries = []
    for i, chunk_text in enumerate(chunks):
        entries.append({
            "chunk_id": str(uuid.uuid4()),
            "document_id": document_id,
            "document_title": title,
            "text": chunk_text,
            "position": i,
        })
    _document_store[document_id] = entries


def search_similar(query: str, top_k: int = 5) -> str:
    """Search for chunks similar to the query using keyword matching.

    Args:
        query: The search query string.
        top_k: Maximum number of results to return.

    Returns:
        Formatted string of matching chunks.
    """
    query_words = set(query.lower().split())
    scored: list[tuple[float, dict]] = []

    for doc_chunks in _document_store.values():
        for chunk in doc_chunks:
            chunk_words = set(chunk["text"].lower().split())
            overlap = len(query_words & chunk_words)
            if overlap > 0:
                score = overlap / max(len(query_words), 1)
                scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_results = scored[:top_k]

    if not top_results:
        return "No relevant documents found."

    parts: list[str] = []
    for score, chunk in top_results:
        parts.append(
            f"[{chunk['document_title']}] (score: {score:.2f})\n{chunk['text']}"
        )
    return "\n\n---\n\n".join(parts)
