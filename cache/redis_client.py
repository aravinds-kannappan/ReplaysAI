import json
from typing import Any, Optional
import redis
from config import get_settings

_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        settings = get_settings()
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def cache_get(key: str) -> Optional[Any]:
    try:
        val = get_redis().get(key)
        return json.loads(val) if val else None
    except Exception:
        return None


def cache_set(key: str, value: Any, ttl: Optional[int] = None) -> None:
    try:
        serialized = json.dumps(value)
        if ttl:
            get_redis().setex(key, ttl, serialized)
        else:
            get_redis().set(key, serialized)
    except Exception:
        pass


def cache_delete(key: str) -> None:
    try:
        get_redis().delete(key)
    except Exception:
        pass
