"""Rate limiter setup using slowapi + Redis."""

from slowapi import Limiter
from slowapi.util import get_remote_address


def build_limiter(
    redis_url: str = "redis://localhost:6379",
    *,
    default_limit: str = "60/minute",
) -> Limiter:
    """Build a configured slowapi Limiter backed by Redis.

    Args:
        redis_url: Redis connection URL.
        default_limit: Default rate limit string (e.g., "60/minute", "100/hour").

    Returns:
        A configured Limiter instance ready to be attached to a FastAPI app.

    Usage:
        limiter = build_limiter("redis://localhost:6379")
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

        @app.get("/endpoint")
        @limiter.limit("10/minute")
        async def endpoint(request: Request):
            ...
    """
    return Limiter(
        key_func=get_remote_address,
        default_limits=[default_limit],
        storage_uri=redis_url,
    )
