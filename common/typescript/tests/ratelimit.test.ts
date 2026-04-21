import { describe, it, expect } from "vitest";
import { buildRateLimiter } from "../src/ratelimit/ratelimit.js";

describe("ratelimit", () => {
  it("allows requests within limit", () => {
    const limiter = buildRateLimiter({
      redisUrl: "redis://localhost:6379",
      maxRequests: 3,
      windowSeconds: 60,
    });

    expect(limiter("user-1").allowed).toBe(true);
    expect(limiter("user-1").allowed).toBe(true);
    expect(limiter("user-1").allowed).toBe(true);
  });

  it("blocks requests over limit", () => {
    const limiter = buildRateLimiter({
      redisUrl: "redis://localhost:6379",
      maxRequests: 2,
      windowSeconds: 60,
    });

    expect(limiter("user-2").allowed).toBe(true);
    expect(limiter("user-2").allowed).toBe(true);
    expect(limiter("user-2").allowed).toBe(false);
    expect(limiter("user-2").remaining).toBe(0);
  });

  it("tracks users independently", () => {
    const limiter = buildRateLimiter({
      redisUrl: "redis://localhost:6379",
      maxRequests: 1,
      windowSeconds: 60,
    });

    expect(limiter("user-a").allowed).toBe(true);
    expect(limiter("user-b").allowed).toBe(true);
    expect(limiter("user-a").allowed).toBe(false);
  });
});
