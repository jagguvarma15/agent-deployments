import { describe, it, expect } from "vitest";
import { ClassificationResult, Intent, TriageRequest } from "../../src/schemas/index.js";

describe("schemas", () => {
  it("validates classification result", () => {
    const result = ClassificationResult.parse({
      intent: "billing",
      confidence: 0.95,
      reasoning: "Customer mentions billing",
    });
    expect(result.intent).toBe("billing");
  });

  it("rejects invalid intent", () => {
    expect(() =>
      ClassificationResult.parse({
        intent: "invalid",
        confidence: 0.5,
        reasoning: "test",
      }),
    ).toThrow();
  });

  it("validates triage request", () => {
    const req = TriageRequest.parse({ message: "Help me", user_id: "user-1" });
    expect(req.message).toBe("Help me");
  });

  it("rejects empty message", () => {
    expect(() => TriageRequest.parse({ message: "", user_id: "user-1" })).toThrow();
  });

  it("has all intent values", () => {
    expect(Intent.options).toEqual(["billing", "technical", "account", "general"]);
  });
});
