import { describe, expect, it } from "vitest";
import { ResearchRequest, ResearchResult } from "../../src/schemas/index.js";

describe("ResearchRequest", () => {
  it("parses valid request", () => {
    const result = ResearchRequest.parse({ question: "test" });
    expect(result.question).toBe("test");
    expect(result.max_steps).toBe(5);
  });

  it("rejects empty question", () => {
    expect(() => ResearchRequest.parse({ question: "" })).toThrow();
  });
});

describe("ResearchResult", () => {
  it("parses valid result", () => {
    const result = ResearchResult.parse({
      id: "abc",
      question: "test",
      steps: [{ step: 1, action: "search", content: "searching" }],
      answer: "answer",
      sources: [{ title: "t", url: "u", excerpt: "e" }],
      trace_id: "trace",
    });
    expect(result.id).toBe("abc");
  });
});
