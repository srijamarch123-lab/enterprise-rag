import os
import logging
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Fallback in-memory store
_local_store = {}
_local_lock = threading.Lock()


class LocalRedisFallback:
    """Thread-safe in-memory key-value store with expiry, mimicing subset of redis-py interfaces."""

    def get(self, key: str) -> str | None:
        with _local_lock:
            val = _local_store.get(key)
            if val:
                expire_at, value_str = val
                if expire_at and datetime.utcnow() > expire_at:
                    _local_store.pop(key, None)
                    return None
                return value_str
            return None

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        with _local_lock:
            expire_at = None
            if ex:
                expire_at = datetime.utcnow() + timedelta(seconds=ex)
            _local_store[key] = (expire_at, value)
            return True

    def delete(self, key: str) -> int:
        with _local_lock:
            return 1 if _local_store.pop(key, None) is not None else 0


_redis_client = None
_use_fallback = True


def init_redis():
    global _redis_client, _use_fallback
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        logger.info("REDIS_URL not configured. Using local in-memory fallback store.")
        _redis_client = LocalRedisFallback()
        _use_fallback = True
        return

    try:
        import redis
        client = redis.from_url(
            redis_url,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
            decode_responses=True,
        )
        client.ping()
        _redis_client = client
        _use_fallback = False
        logger.info("Connected to Redis successfully.")
    except Exception as exc:
        logger.warning(
            "Failed to connect to Redis or redis package not installed, falling back to local in-memory store. Error: %s",
            exc,
        )
        _redis_client = LocalRedisFallback()
        _use_fallback = True


def get_redis_client():
    global _redis_client
    if _redis_client is None:
        init_redis()
    return _redis_client
