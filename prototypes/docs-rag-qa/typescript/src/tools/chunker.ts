/**
 * Document chunking utility.
 */

export function chunkDocument(
  content: string,
  chunkSize = 500,
  overlap = 50,
): string[] {
  if (!content.trim()) return [];

  const sentences = content.match(/[^.!?]+[.!?]+\s*/g) ?? [content];
  const chunks: string[] = [];
  let current = "";

  for (const sentence of sentences) {
    if (current.length + sentence.length > chunkSize && current.length > 0) {
      chunks.push(current.trim());
      // Keep overlap from end of previous chunk
      const words = current.split(/\s+/);
      const overlapWords = words.slice(
        Math.max(0, words.length - Math.ceil(overlap / 5)),
      );
      current = `${overlapWords.join(" ")} ${sentence}`;
    } else {
      current += sentence;
    }
  }

  if (current.trim()) {
    chunks.push(current.trim());
  }

  return chunks;
}
