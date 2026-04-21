import { describe, it, expect } from "vitest";
import { createLogger } from "../src/logging/logger.js";

describe("logging", () => {
  it("creates a logger with service name", () => {
    const logger = createLogger({ serviceName: "test-service" });
    expect(logger).toBeDefined();
  });

  it("creates a logger with custom level", () => {
    const logger = createLogger({
      serviceName: "test-service",
      level: "debug",
      env: "production",
    });
    expect(logger).toBeDefined();
  });
});
