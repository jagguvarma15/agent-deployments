"""Document chunking utilities."""

import re


def chunk_document(content: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks by sentence boundaries.

    Args:
        content: The text to split into chunks.
        chunk_size: Target size for each chunk in characters.
        overlap: Number of characters to overlap between chunks.

    Returns:
        A list of text chunks.
    """
    if not content or not content.strip():
        return []

    # Split into sentences using common delimiters
    sentences = re.split(r"(?<=[.!?])\s+", content.strip())
    sentences = [s for s in sentences if s.strip()]

    if not sentences:
        return []

    chunks: list[str] = []
    current_chunk = ""

    for sentence in sentences:
        candidate = f"{current_chunk} {sentence}".strip() if current_chunk else sentence

        if len(candidate) > chunk_size and current_chunk:
            chunks.append(current_chunk)
            # Apply overlap: take the tail of the current chunk
            if overlap > 0 and len(current_chunk) > overlap:
                current_chunk = current_chunk[-overlap:] + " " + sentence
            else:
                current_chunk = sentence
        else:
            current_chunk = candidate

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks
