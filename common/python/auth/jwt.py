"""JWT utilities for FastAPI-based agent prototypes."""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

_security = HTTPBearer()

# Defaults — override via environment / pydantic-settings in each prototype
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
