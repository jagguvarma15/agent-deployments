import { describe, it, expect } from "vitest";
import { traced, createLangfuseClient } from "../src/observability/langfuse.js";

describe("observability", () => {
  it("traced executes the wrapped function", async () => {
    const result = await traced("test-op", async () => {
      return 42;
    });
    expect(result).toBe(42);
  });

  it("traced propagates errors", async () => {
    await expect(
      traced("failing-op", async () => {
        throw new Error("test error");
      }),
    ).rejects.toThrow("test error");
  });

  it("createLangfuseClient returns config", () => {
    const config = createLangfuseClient({
      publicKey: "pk-test",
      secretKey: "sk-test",
      host: "http://localhost:3000",
    });
    expect(config.publicKey).toBe("pk-test");
  });
});
