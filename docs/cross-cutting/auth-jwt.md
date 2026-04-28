# Cross-cutting: JWT Authentication

**Concern:** Protect all agent endpoints with bearer-token authentication.
**Library:** `python-jose` (Py) / `jose` (TS)
**Lives in:** `common/python/agent_common/auth/` and `common/typescript/src/auth/`

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

- **Python:** `common/python/tests/test_auth.py` -- token creation, verification, expiry, invalid tokens, FastAPI dependency
- **TypeScript:** `common/typescript/tests/auth.test.ts` -- token round-trip, expiry, invalid signature

## Production considerations

- **HS256 is fine for local dev** where the secret is in `.env`. For production, switch to **RS256** with asymmetric keys so the API only needs the public key.
- **Token rotation:** The current implementation has no refresh token flow. For production, add a `/refresh` endpoint or use short-lived tokens with an external auth provider.
- **Extra claims:** Pass `extra={"role": "admin"}` to embed authorization data in the token. The payload is available in the endpoint handler.

## Swapping to an external auth provider

To use Auth0, Clerk, or Supabase Auth instead of self-managed JWT:

1. Replace `create_token()` with the provider's token issuance (usually handled by their SDK).
2. Replace `verify_token()` with JWKS-based verification against the provider's public keys.
3. Keep the `get_current_user` dependency shape -- just change the verification logic inside.

This is a **single-file swap** (only `common/auth/jwt.py` or `jwt.ts` changes).
