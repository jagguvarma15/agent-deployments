import { describe, expect, it } from "vitest";
import { chunkDocument } from "../../src/tools/chunker.js";

describe("chunkDocument", () => {
  it("splits long text into chunks", () => {
    const text =
      "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence.";
    const chunks = chunkDocument(text, 40, 10);
    expect(chunks.length).toBeGreaterThan(1);
  });

  it("returns single chunk for short text", () => {
    const chunks = chunkDocument("Short text.", 500, 50);
    expect(chunks).toHaveLength(1);
    expect(chunks[0]).toBe("Short text.");
  });

  it("returns empty array for empty input", () => {
    const chunks = chunkDocument("", 500, 50);
    expect(chunks).toHaveLength(0);
  });

  it("handles text without sentence boundaries", () => {
    const text = "No sentence endings here";
    const chunks = chunkDocument(text, 500, 50);
    expect(chunks).toHaveLength(1);
    expect(chunks[0]).toBe("No sentence endings here");
  });
});
