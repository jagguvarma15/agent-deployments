import { describe, it, expect } from "vitest";
import { createToken, verifyToken } from "../src/auth/jwt.js";

const SECRET = "test-secret-key-for-unit-tests";

describe("auth/jwt", () => {
  it("creates and verifies a token", async () => {
    const token = await createToken("user-123", SECRET);
    const payload = await verifyToken(token, SECRET);
    expect(payload.sub).toBe("user-123");
  });

  it("includes extra claims", async () => {
    const token = await createToken("user-456", SECRET, {
      extra: { role: "admin" },
    });
    const payload = await verifyToken(token, SECRET);
    expect(payload.sub).toBe("user-456");
    expect(payload.role).toBe("admin");
  });

  it("rejects invalid tokens", async () => {
    await expect(verifyToken("not-a-real-token", SECRET)).rejects.toThrow();
  });

  it("rejects tokens with wrong secret", async () => {
    const token = await createToken("user-789", SECRET);
    await expect(verifyToken(token, "wrong-secret")).rejects.toThrow();
  });
});
