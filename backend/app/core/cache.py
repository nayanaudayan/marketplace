"""Best-effort Redis helpers. Redis is never the source of truth: every call degrades gracefully."""
import json
import time
from typing import Any

import redis

from app.core.config import settings

_client: redis.Redis | None = None
_local_windows: dict[str, tuple[float, int]] = {}


def _redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.redis_url, socket_timeout=0.3, socket_connect_timeout=0.3)
    return _client


def cache_get(key: str) -> Any | None:
    try:
        raw = _redis().get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    try:
        _redis().setex(key, ttl, json.dumps(value))
    except Exception:
        pass


def cache_delete(key: str) -> None:
    try:
        _redis().delete(key)
    except Exception:
        pass


def rate_limit(key: str, limit: int, window_seconds: int = 60) -> bool:
    """Fixed-window limiter. Returns True if the request is allowed. Falls back to in-process counters."""
    try:
        r = _redis()
        bucket = f"rl:{key}:{int(time.time() // window_seconds)}"
        count = r.incr(bucket)
        if count == 1:
            r.expire(bucket, window_seconds)
        return count <= limit
    except Exception:
        now = time.time()
        start, count = _local_windows.get(key, (now, 0))
        if now - start >= window_seconds:
            start, count = now, 0
        _local_windows[key] = (start, count + 1)
        return count + 1 <= limit
