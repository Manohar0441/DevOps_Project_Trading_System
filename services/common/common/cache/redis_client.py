from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

try:
    import redis as _redis_lib
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False


class RedisClient:
    """JSON-serialising Redis wrapper with graceful degradation when Redis is unavailable."""

    def __init__(self) -> None:
        self._client = None
        if not _REDIS_AVAILABLE:
            logger.warning("redis-py not installed; caching disabled")
            return

        host = os.environ.get("REDIS_HOST", "localhost")
        port = int(os.environ.get("REDIS_PORT", "6379"))
        try:
            self._client = _redis_lib.Redis(
                host=host, port=port, decode_responses=True, socket_timeout=2, socket_connect_timeout=2
            )
            self._client.ping()
            logger.info("Redis connected at %s:%s", host, port)
        except Exception as exc:
            logger.warning("Redis unavailable (%s); caching disabled", exc)
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def get(self, key: str) -> Any | None:
        if not self._client:
            return None
        try:
            raw = self._client.get(key)
            return json.loads(raw) if raw is not None else None
        except Exception as exc:
            logger.debug("Redis get error for key=%s: %s", key, exc)
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        if not self._client:
            return
        try:
            self._client.setex(key, ttl, json.dumps(value, default=str))
        except Exception as exc:
            logger.debug("Redis set error for key=%s: %s", key, exc)

    def delete(self, key: str) -> None:
        if not self._client:
            return
        try:
            self._client.delete(key)
        except Exception as exc:
            logger.debug("Redis delete error for key=%s: %s", key, exc)


_default: RedisClient | None = None


def get_redis() -> RedisClient:
    global _default
    if _default is None:
        _default = RedisClient()
    return _default
