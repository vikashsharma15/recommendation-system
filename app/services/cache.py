"""
Cache layer — Upstash Redis (production) / in-memory fallback (dev).

Latency targets:
  Redis HIT  → < 10ms
  Memory HIT → < 1ms
  MISS       → caller decides (Pinecone ~200-500ms)

Thread safety: Lock guards both _redis init and _mem_store mutations.
"""

import json
import logging
import threading
import time
from typing import Any, Optional

from app.core.config import get_settings

logger   = logging.getLogger(__name__)
settings = get_settings()

# ── Thread-safe in-memory store ────────────────────────────
# { key → (value, expires_at_unix) }
_mem_store: dict[str, tuple[Any, float]] = {}
_mem_lock  = threading.Lock()

# ── Redis singleton (thread-safe init) ─────────────────────
_redis      = None
_redis_lock = threading.Lock()
_redis_dead = False   # once init fails, skip retries for this process lifetime


def _get_redis():
    """
    Return a live Redis client or None.

    Double-checked locking so only ONE thread pays the import+connect cost.
    _redis_dead short-circuits after a permanent init failure so every
    request doesn't retry the slow import path.
    """
    global _redis, _redis_dead

    if _redis_dead:
        return None
    if _redis is not None:
        return _redis

    with _redis_lock:
        if _redis is not None:          # another thread won the race
            return _redis
        if _redis_dead:
            return None

        url   = settings.upstash_redis_rest_url
        token = settings.upstash_redis_rest_token
        if not url or not token:
            logger.info("Redis not configured — using in-memory cache")
            _redis_dead = True
            return None

        try:
            from upstash_redis import Redis
            client = Redis(url=url, token=token)
            client.ping()               # validate connection now, not lazily
            _redis = client
            logger.info("Redis connected ✓")
        except Exception as exc:
            logger.warning("Redis init failed — falling back to in-memory: %s", exc)
            _redis_dead = True
            return None

    return _redis


# ── Core operations ────────────────────────────────────────

def get(key: str) -> Optional[Any]:
    """
    Return cached value or None.

    Never raises — Redis errors fall through to in-memory, then return None.
    """
    redis = _get_redis()
    if redis:
        try:
            raw = redis.get(key)
            if raw is not None:
                logger.debug("Cache HIT  redis  key=%s", key)
                return json.loads(raw)
            logger.debug("Cache MISS redis  key=%s", key)
            return None
        except Exception as exc:
            logger.warning("Redis GET error key=%s: %s — trying memory", key, exc)

    # in-memory fallback
    with _mem_lock:
        entry = _mem_store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() < expires_at:
            logger.debug("Cache HIT  memory key=%s", key)
            return value
        # expired — evict eagerly
        del _mem_store[key]
        return None


def set(key: str, value: Any, ttl: Optional[int] = None) -> None:
    """
    Store value with TTL (seconds).  Silently no-ops on error.
    """
    if value is None:
        # Don't cache None — would mask a real MISS on next request
        return

    ttl = ttl or settings.cache_ttl_seconds

    redis = _get_redis()
    if redis:
        try:
            redis.set(key, json.dumps(value), ex=ttl)
            logger.debug("Cache SET  redis  key=%s ttl=%ds", key, ttl)
            return
        except Exception as exc:
            logger.warning("Redis SET error key=%s: %s — writing to memory", key, exc)

    # in-memory fallback
    expires_at = time.monotonic() + ttl
    with _mem_lock:
        _mem_store[key] = (value, expires_at)
        _evict_stale_locked()           # inline cleanup, lock already held
    logger.debug("Cache SET  memory key=%s ttl=%ds", key, ttl)


def delete(key: str) -> None:
    redis = _get_redis()
    if redis:
        try:
            redis.delete(key)
            logger.debug("Cache DEL  redis  key=%s", key)
        except Exception as exc:
            logger.warning("Redis DEL error key=%s: %s", key, exc)

    with _mem_lock:
        _mem_store.pop(key, None)


def delete_pattern(pattern: str) -> None:
    """
    Delete all keys matching a glob pattern.
    Edge case: redis.delete(*[]) → passes empty splat — guard with early return.
    """
    prefix = pattern.rstrip("*")

    redis = _get_redis()
    if redis:
        try:
            cursor = 0
            while True:
                cursor, keys = redis.scan(cursor, match=pattern, count=100)
                if keys:                            # ← guard: never call delete(*[])
                    redis.delete(*keys)
                if cursor == 0:
                    break
            logger.debug("Cache DEL pattern=%s", pattern)
        except Exception as exc:
            logger.warning("Redis SCAN/DEL error pattern=%s: %s", pattern, exc)

    prefix = pattern.rstrip("*")
    with _mem_lock:
        stale = [k for k in _mem_store if k.startswith(prefix)]
        for k in stale:
            del _mem_store[k]


def exists(key: str) -> bool:
    """
    Prefer cache.get() over exists() — get() is one round-trip that also
    returns data.  exists() is useful only when you need the boolean fast
    without deserialising the payload (e.g. header-only check).
    """
    redis = _get_redis()
    if redis:
        try:
            return bool(redis.exists(key))
        except Exception:
            pass
    with _mem_lock:
        entry = _mem_store.get(key)
        if entry is None:
            return False
        _, expires_at = entry
        return time.monotonic() < expires_at


def get_ttl(key: str) -> Optional[int]:
    """Remaining TTL in seconds. -1 = no TTL. -2 / None = key missing."""
    redis = _get_redis()
    if redis:
        try:
            return redis.ttl(key)
        except Exception:
            pass
    with _mem_lock:
        entry = _mem_store.get(key)
        if entry is None:
            return None
        _, expires_at = entry
        return max(0, int(expires_at - time.monotonic()))


# ── Private helpers ────────────────────────────────────────

def _evict_stale_locked() -> None:
    """
    Simple LRU-style eviction.  Caller must hold _mem_lock.
    Runs only when store is large to keep hot-path overhead zero.
    """
    if len(_mem_store) <= 400:
        return
    now   = time.monotonic()
    stale = [k for k, (_, exp) in _mem_store.items() if exp < now]
    for k in stale:
        del _mem_store[k]
    # If still too large after TTL eviction, drop oldest 20 %
    if len(_mem_store) > 500:
        overflow = len(_mem_store) - 400
        for k in list(_mem_store)[:overflow]:
            del _mem_store[k]


# ── Key builders ───────────────────────────────────────────

def make_recommend_key(user_id: int) -> str:
    return f"recommend:user:{user_id}"

def make_recommend_page_key(user_id: int, page: int) -> str:
    return f"recommend:user:{user_id}:page:{page}"

def make_groq_key(user_id: int) -> str:
    return f"groq:user:{user_id}"

def make_user_key(user_id: int) -> str:
    return f"user:profile:{user_id}"

def make_user_pattern(user_id: int) -> str:
    """Glob to nuke ALL cache entries for one user."""
    return f"*:user:{user_id}*"


# ── Health check ───────────────────────────────────────────

def ping() -> dict:
    redis = _get_redis()
    if not redis:
        with _mem_lock:
            key_count = len(_mem_store)
        return {"backend": "memory", "status": "ok", "keys": key_count}
    try:
        redis.ping()
        return {"backend": "redis", "status": "ok"}
    except Exception as exc:
        return {"backend": "redis", "status": "error", "error": str(exc)}