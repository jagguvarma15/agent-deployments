import { describe, it, expect } from "vitest";
import { MCPClient } from "../src/mcp/client.js";

describe("MCPClient", () => {
  it("initializes with base url", () => {
    const client = new MCPClient({ baseUrl: "http://localhost:3001" });
    expect(client.baseUrl).toBe("http://localhost:3001");
    expect(client.timeoutMs).toBe(30_000);
  });

  it("accepts custom headers and timeout", () => {
    const client = new MCPClient({
      baseUrl: "http://localhost:3001",
      headers: { Authorization: "Bearer test" },
      timeoutMs: 60_000,
    });
    expect(client.headers.Authorization).toBe("Bearer test");
    expect(client.timeoutMs).toBe(60_000);
  });
});
