from __future__ import annotations

from functools import lru_cache

from redis import Redis
from redis.exceptions import RedisError

from config import settings


@lru_cache(maxsize=1)
def get_redis_connection() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=False)


def redis_ping() -> bool:
    """Return True when Redis responds to PING."""
    try:
        return bool(get_redis_connection().ping())
    except RedisError:
        return False


def get_redis_or_none() -> Redis | None:
    """Return Redis when reachable; None when unavailable (auth degrade mode)."""
    if not redis_ping():
        return None
    return get_redis_connection()
