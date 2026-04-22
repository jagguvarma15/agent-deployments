import { describe, it, expect } from "vitest";
import { stripeLookup } from "../../src/tools/stripe.js";
import { mockSearch } from "../../src/tools/kb.js";

describe("stripe tool", () => {
  it("returns charge info for charge queries", async () => {
    const result = await stripeLookup("check charge history");
    expect(result).toContain("$49.00");
  });

  it("returns subscription info", async () => {
    const result = await stripeLookup("current subscription");
    expect(result.toLowerCase()).toContain("subscription");
  });

  it("returns customer overview for generic queries", async () => {
    const result = await stripeLookup("general info");
    expect(result).toContain("cus_demo123");
  });
});

describe("kb tool", () => {
  it("finds password reset article", () => {
    const result = mockSearch("reset password");
    expect(result.toLowerCase()).toContain("password");
  });

  it("finds technical articles for API errors", () => {
    const result = mockSearch("API rate limit error");
    expect(result.toLowerCase()).toMatch(/rate limit|429/);
  });

  it("returns no results for gibberish", () => {
    const result = mockSearch("xyzzy foobar baz");
    expect(result).toContain("No relevant articles");
  });
});
