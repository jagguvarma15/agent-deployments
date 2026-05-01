# Cross-cutting: JWT Authentication

**Concern:** Protect all agent endpoints with bearer-token authentication.
**Library:** `python-jose` (Py) / `jose` (TS)
**Lives in:** Inline below (formerly `common/python/agent_common/auth/` and `common/typescript/src/auth/`)

## What it provides

- **Token creation** -- `create_token()` / `createToken()` signs a JWT with a user ID, expiry, and optional extra claims.
- **Token verification** -- `verify_token()` / `verifyToken()` decodes and validates a JWT, returning a typed payload.
- **FastAPI dependency** -- `get_current_user(secret)` returns a FastAPI `Depends()` that extracts the bearer token from the `Authorization` header, verifies it, and returns a `TokenPayload`. Returns 401 on failure.
- **Typed payload** -- `TokenPayload` model (Pydantic / TS interface) with `sub`, `exp`, and extra claims.

## How to use

### Python (FastAPI)

```python
from agent_common.auth import create_token, get_current_user, TokenPayload

# Create a token (for testing or a /login endpoint)
token = create_token("user-123", secret="my-secret", expires_hours=24)

# Protect an endpoint
@app.post("/query")
async def query(
    request: QueryRequest,
    user: TokenPayload = Depends(get_current_user("my-secret")),
):
    # user.sub is the authenticated user ID
    return await handle_query(request, user_id=user.sub)
```

### TypeScript (Hono)

```typescript
import { createToken, verifyToken } from "@agent-deployments/common";

// Create a token
const token = await createToken("user-123", "my-secret");

// Verify in middleware
app.use("/query/*", async (c, next) => {
  const auth = c.req.header("Authorization");
  const token = auth?.replace("Bearer ", "");
  if (!token) return c.json({ error: "Unauthorized" }, 401);

  try {
    const payload = await verifyToken(token, "my-secret");
    c.set("userId", payload.sub);
    await next();
  } catch {
    return c.json({ error: "Invalid token" }, 401);
  }
});
```

## Configuration via env

| Var | Default | Effect |
|-----|---------|--------|
| `JWT_SECRET` | `change-me-in-production` | Signing secret (HS256) |
| Algorithm | `HS256` | Symmetric signing for local dev. Switch to RS256 with a key pair for production |
| Expiry | 24 hours | Token lifetime |

## Tests

Test token creation, verification, expiry, invalid tokens, and the FastAPI dependency (Py) / token round-trip and invalid signature (TS).

## Production considerations

- **HS256 is fine for local dev** where the secret is in `.env`. For production, switch to **RS256** with asymmetric keys so the API only needs the public key.
- **Token rotation:** The current implementation has no refresh token flow. For production, add a `/refresh` endpoint or use short-lived tokens with an external auth provider.
- **Extra claims:** Pass `extra={"role": "admin"}` to embed authorization data in the token. The payload is available in the endpoint handler.

## Swapping to an external auth provider

To use Auth0, Clerk, or Supabase Auth instead of self-managed JWT:

1. Replace `create_token()` with the provider's token issuance (usually handled by their SDK).
2. Replace `verify_token()` with JWKS-based verification against the provider's public keys.
3. Keep the `get_current_user` dependency shape -- just change the verification logic inside.

This is a **single-file swap** (only the auth module changes).

## Reference Implementation

<details>
<summary>Python — <code>jwt.py</code></summary>

```python
"""JWT utilities for FastAPI-based agent prototypes."""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

_security = HTTPBearer()

_DEFAULT_ALGORITHM = "HS256"
_DEFAULT_EXPIRY_HOURS = 24


class TokenPayload(BaseModel):
    sub: str
    exp: datetime
    extra: dict[str, Any] = {}


def create_token(
    user_id: str,
    secret: str,
    *,
    algorithm: str = _DEFAULT_ALGORITHM,
    expires_hours: int = _DEFAULT_EXPIRY_HOURS,
    extra: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT."""
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(hours=expires_hours),
        **(extra or {}),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def verify_token(
    token: str,
    secret: str,
    *,
    algorithm: str = _DEFAULT_ALGORITHM,
) -> TokenPayload:
    """Verify and decode a JWT. Raises ValueError on failure."""
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        return TokenPayload(
            sub=payload["sub"],
            exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
            extra={k: v for k, v in payload.items() if k not in ("sub", "exp", "iat")},
        )
    except JWTError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc


def get_current_user(
    secret: str,
    algorithm: str = _DEFAULT_ALGORITHM,
):
    """Return a FastAPI dependency that extracts and verifies the JWT bearer token."""

    async def _dependency(
        credentials: HTTPAuthorizationCredentials = Depends(_security),
    ) -> TokenPayload:
        try:
            return verify_token(credentials.credentials, secret, algorithm=algorithm)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

    return _dependency
```

</details>

<details>
<summary>TypeScript — <code>jwt.ts</code></summary>

```typescript
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
```

</details>
