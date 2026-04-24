import { describe, expect, it } from "vitest";
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

describe("documents endpoint", () => {
  it("rejects invalid ingest requests", async () => {
    const { documentsRouter } = await import(
      "../../src/api/documents.js"
    );
    const app = new Hono();
    app.route("/", documentsRouter);

    const res = await app.request("/documents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: "", title: "" }),
    });
    expect(res.status).toBe(400);
  });

  it("ingests valid documents", async () => {
    const { documentsRouter } = await import(
      "../../src/api/documents.js"
    );
    const app = new Hono();
    app.route("/", documentsRouter);

    const res = await app.request("/documents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: "This is a test document with content.",
        title: "Test Doc",
      }),
    });
    expect(res.status).toBe(200);

    const body = await res.json();
    expect(body.document_id).toBeDefined();
    expect(body.chunk_count).toBeGreaterThan(0);
    expect(body.status).toBe("ingested");
  });
});
