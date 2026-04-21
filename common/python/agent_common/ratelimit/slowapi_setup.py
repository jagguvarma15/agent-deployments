"""Rate limiter setup using slowapi + Redis."""

from slowapi import Limiter
from slowapi.util import get_remote_address


def build_limiter(
    redis_url: str = "redis://localhost:6379",
    *,
    default_limit: str = "60/minute",
) -> Limiter:
    """Build a configured slowapi Limiter backed by Redis."""
    return Limiter(
        key_func=get_remote_address,
        default_limits=[default_limit],
        storage_uri=redis_url,
    )
