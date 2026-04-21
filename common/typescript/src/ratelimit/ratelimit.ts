/**
 * Rate limiting utilities for Hono-based prototypes.
 */

export interface RateLimitConfig {
  /** Redis URL for distributed rate limiting */
  redisUrl: string;
  /** Max requests per window */
  maxRequests: number;
  /** Window size in seconds */
  windowSeconds: number;
}

interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  resetAt: number;
}

/**
 * Build a rate limiter function.
 *
 * Returns a function that checks whether a given key (e.g., user ID or IP)
 * is within its rate limit. Uses a simple in-memory sliding window for now;
 * Redis-backed implementation should be added per prototype.
 */
export function buildRateLimiter(config: RateLimitConfig) {
  const windows = new Map<string, { count: number; resetAt: number }>();

  return (key: string): RateLimitResult => {
    const now = Date.now();
    const entry = windows.get(key);

    if (!entry || now >= entry.resetAt) {
      windows.set(key, {
        count: 1,
        resetAt: now + config.windowSeconds * 1000,
      });
      return {
        allowed: true,
        remaining: config.maxRequests - 1,
        resetAt: now + config.windowSeconds * 1000,
      };
    }

    entry.count++;
    const allowed = entry.count <= config.maxRequests;
    return {
      allowed,
      remaining: Math.max(0, config.maxRequests - entry.count),
      resetAt: entry.resetAt,
    };
  };
}
