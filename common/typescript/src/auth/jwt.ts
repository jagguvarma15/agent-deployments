/**
 * JWT utilities for Hono-based agent prototypes.
 */

import * as jose from "jose";

export interface TokenPayload {
  sub: string;
  exp: number;
  iat: number;
  [key: string]: unknown;
}

const DEFAULT_ALGORITHM = "HS256";
const DEFAULT_EXPIRY_HOURS = 24;

/**
 * Create a signed JWT.
 */
export async function createToken(
  userId: string,
  secret: string,
  options: {
    algorithm?: string;
    expiresHours?: number;
    extra?: Record<string, unknown>;
  } = {},
): Promise<string> {
  const { expiresHours = DEFAULT_EXPIRY_HOURS, extra = {} } = options;

  const secretKey = new TextEncoder().encode(secret);
  const now = Math.floor(Date.now() / 1000);

  return new jose.SignJWT({ sub: userId, ...extra })
    .setProtectedHeader({ alg: DEFAULT_ALGORITHM })
    .setIssuedAt(now)
    .setExpirationTime(now + expiresHours * 3600)
    .sign(secretKey);
}

/**
 * Verify and decode a JWT. Throws on failure.
 */
export async function verifyToken(
  token: string,
  secret: string,
  options: { algorithm?: string } = {},
): Promise<TokenPayload> {
  const secretKey = new TextEncoder().encode(secret);

  const { payload } = await jose.jwtVerify(token, secretKey, {
    algorithms: [DEFAULT_ALGORITHM],
  });

  return payload as TokenPayload;
}
