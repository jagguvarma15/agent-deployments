import { describe, expect, it } from "vitest";
import {
  Citation,
  DocumentIngestRequest,
  QueryRequest,
} from "../../src/schemas/index.js";

describe("schemas", () => {
  it("validates DocumentIngestRequest", () => {
    const req = DocumentIngestRequest.parse({
      content: "Some document text",
      title: "My Doc",
    });
    expect(req.content).toBe("Some document text");
    expect(req.title).toBe("My Doc");
  });

  it("rejects empty content", () => {
    expect(() =>
      DocumentIngestRequest.parse({ content: "", title: "Doc" }),
    ).toThrow();
  });

  it("validates QueryRequest with defaults", () => {
    const req = QueryRequest.parse({ question: "What is RAG?" });
    expect(req.question).toBe("What is RAG?");
    expect(req.top_k).toBe(5);
  });

  it("validates Citation", () => {
    const citation = Citation.parse({
      chunk_id: "c-1",
      document_title: "Doc",
      text: "relevant text",
      score: 0.95,
    });
    expect(citation.score).toBe(0.95);
  });
});
