/**
 * In-memory mock vector store with keyword-based retrieval.
 */

interface StoredChunk {
  chunkId: string;
  documentTitle: string;
  text: string;
}

const documentStore: Map<string, StoredChunk[]> = new Map();

export function storeChunks(
  documentId: string,
  title: string,
  chunks: string[],
): void {
  const stored: StoredChunk[] = chunks.map((text, i) => ({
    chunkId: `${documentId}-chunk-${i}`,
    documentTitle: title,
    text,
  }));
  documentStore.set(documentId, stored);
}

export function searchSimilar(query: string, topK = 5): string {
  const words = query.toLowerCase().split(/\s+/);
  const scored: Array<[number, StoredChunk]> = [];

  for (const chunks of documentStore.values()) {
    for (const chunk of chunks) {
      const text = chunk.text.toLowerCase();
      const score = words.filter((w) => text.includes(w)).length;
      if (score > 0) scored.push([score, chunk]);
    }
  }

  scored.sort((a, b) => b[0] - a[0]);
  const top = scored.slice(0, topK);

  if (top.length === 0) {
    return "No relevant documents found.";
  }

  return top
    .map(
      ([score, chunk]) =>
        `[${chunk.documentTitle}] (score: ${score})\n${chunk.text}`,
    )
    .join("\n\n---\n\n");
}

export function clearStore(): void {
  documentStore.clear();
}
