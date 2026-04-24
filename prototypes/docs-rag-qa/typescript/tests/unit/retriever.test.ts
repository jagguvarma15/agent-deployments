import { afterEach, describe, expect, it } from "vitest";
import {
  clearStore,
  searchSimilar,
  storeChunks,
} from "../../src/tools/retriever.js";

describe("retriever", () => {
  afterEach(() => {
    clearStore();
  });

  it("stores and retrieves chunks by keyword", () => {
    storeChunks("doc-1", "Test Doc", [
      "Python is a programming language.",
      "JavaScript runs in the browser.",
    ]);
    const result = searchSimilar("Python programming");
    expect(result).toContain("Python");
    expect(result).toContain("Test Doc");
  });

  it("returns no results for unrelated query", () => {
    storeChunks("doc-1", "Test Doc", ["Hello world content."]);
    const result = searchSimilar("xyzzy foobar baz");
    expect(result).toContain("No relevant documents");
  });

  it("respects top_k limit", () => {
    storeChunks("doc-1", "Doc", [
      "Alpha content here.",
      "Beta content here.",
      "Gamma content here.",
    ]);
    const result = searchSimilar("content", 1);
    const sections = result.split("---");
    expect(sections.length).toBeLessThanOrEqual(2);
  });
});
