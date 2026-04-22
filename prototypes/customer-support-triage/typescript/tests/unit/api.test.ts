import { describe, it, expect } from "vitest";
import { Hono } from "hono";

describe("health endpoint", () => {
  it("returns 200 ok", async () => {
    const app = new Hono();
    app.get("/health", (c) => c.json({ status: "ok" }));

    const res = await app.request("/health");
    expect(res.status).toBe(200);

    const body = await res.json();
    expect(body).toEqual({ status: "ok" });
  });
});

describe("triage request validation", () => {
  it("rejects invalid requests", async () => {
    // Import the router which has validation
    const { triageRouter } = await import("../../src/api/triage.js");
    const app = new Hono();
    app.route("/", triageRouter);

    const res = await app.request("/triage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: "", user_id: "" }),
    });
    expect(res.status).toBe(400);
  });
});
