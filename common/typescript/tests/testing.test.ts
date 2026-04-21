import { describe, it, expect } from "vitest";
import { mockLlmResponse, mockLlmClient } from "../src/testing/fixtures.js";

describe("testing fixtures", () => {
  it("creates a mock LLM response with defaults", () => {
    const response = mockLlmResponse();
    expect(response.choices[0]!.message.content).toBe("Hello from mock LLM");
    expect(response.choices[0]!.message.role).toBe("assistant");
  });

  it("creates a mock LLM response with custom content", () => {
    const response = mockLlmResponse("Custom answer", { model: "gpt-4" });
    expect(response.choices[0]!.message.content).toBe("Custom answer");
    expect(response.model).toBe("gpt-4");
  });

  it("mock client returns predefined responses", async () => {
    const client = mockLlmClient(["Response 1", "Response 2"]);
    const r1 = await client.chat.completions.create();
    expect(r1.choices[0]!.message.content).toBe("Response 1");
    const r2 = await client.chat.completions.create();
    expect(r2.choices[0]!.message.content).toBe("Response 2");
  });

  it("mock client cycles through responses", async () => {
    const client = mockLlmClient(["A"]);
    const r1 = await client.chat.completions.create();
    const r2 = await client.chat.completions.create();
    expect(r1.choices[0]!.message.content).toBe("A");
    expect(r2.choices[0]!.message.content).toBe("A");
  });
});
