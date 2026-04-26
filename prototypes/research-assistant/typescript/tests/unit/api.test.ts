import { describe, expect, it } from "vitest";
import app from "../../src/index.js";

describe("health endpoint", () => {
  it("returns ok", async () => {
    const res = await app.request("/health");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toEqual({ status: "ok" });
  });
});

describe("POST /research", () => {
  it("returns a research result", async () => {
    const res = await app.request("/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "What is AI?" }),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.id).toBeDefined();
    expect(body.question).toBe("What is AI?");
    expect(body.steps).toHaveLength(3);
    expect(body.answer).toContain("What is AI?");
    expect(body.sources).toHaveLength(1);
    expect(body.trace_id).toBeDefined();
  });

  it("rejects invalid request", async () => {
    const res = await app.request("/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(400);
  });
});

describe("GET /research/:id/status", () => {
  it("returns not_found for unknown id", async () => {
    const res = await app.request("/research/unknown-id/status");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("not_found");
  });
});
