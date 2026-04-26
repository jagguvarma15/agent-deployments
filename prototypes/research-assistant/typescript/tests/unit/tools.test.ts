import { describe, expect, it } from "vitest";
import { citeSources } from "../../src/tools/cite-sources.js";
import { extractFacts } from "../../src/tools/extract-facts.js";
import { summarize } from "../../src/tools/summarize.js";
import { webSearch } from "../../src/tools/web-search.js";

describe("webSearch", () => {
  it("returns mock results", async () => {
    const result = await webSearch("machine learning");
    expect(result).toContain("Machine Learning");
    expect(result).toContain("Deep Learning");
    expect(result).toContain("NLP");
  });
});

describe("summarize", () => {
  it("returns short text unchanged", () => {
    expect(summarize("short text")).toBe("short text");
  });

  it("truncates long text at word boundary", () => {
    const long = "word ".repeat(100);
    const result = summarize(long, 20);
    expect(result.length).toBeLessThanOrEqual(24);
    expect(result).toMatch(/\.\.\.$/);
  });
});

describe("citeSources", () => {
  it("formats facts with numbered citations", () => {
    const result = citeSources(["fact one", "fact two"]);
    expect(result).toBe("[1] fact one\n[2] fact two");
  });

  it("returns message for empty list", () => {
    expect(citeSources([])).toBe("No facts to cite.");
  });
});

describe("extractFacts", () => {
  it("returns mock facts", () => {
    const facts = extractFacts("some text");
    expect(facts).toHaveLength(3);
    expect(facts[0]).toContain("Machine learning");
  });
});
