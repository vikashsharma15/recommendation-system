"""
Cache layer — Upstash Redis (production) ya in-memory fallback (local dev).

Flow:
  Request aaya
      │
      ▼
  Redis check ──── HIT ──► return cached JSON  (< 5ms)
      │
     MISS
      │
      ▼
  Pinecone search + rerank  (~200-500ms)
      │
      ▼
  Redis mein store (TTL = 5 min)
      │
      ▼
  Return results

Cache keys:
  recommend:user:{id}          — user recommendations (TTL 5 min)
  recommend:user:{id}:page:{p} — per-page cache (TTL 5 min)
  groq:user:{id}               — groq summary (TTL 10 min)
  user:profile:{id}            — user profile (TTL 15 min)
"""

import json
import logging
import time
from typing import Any, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── In-memory fallback ─────────────────────────────────────
# Redis nahi hai toh local dict use karo — dev ke liye
_mem_store: dict[str, tuple[Any, float]] = {}  # key → (value, expires_at)

_redis = None


def _get_redis():
    global _redis
    if _redis is None:
        if not settings.upstash_redis_rest_url or not settings.upstash_redis_rest_token:
            return None
        try:
            from upstash_redis import Redis
            _redis = Redis(
                url=settings.upstash_redis_rest_url,
                token=settings.upstash_redis_rest_token,
            )
            logger.info("Redis connected ✓")
        except Exception as e:
            logger.warning(f"Redis init failed — using in-memory fallback: {e}")
            return None
    return _redis


# ── Core operations ───────────────────────────────────────
def get(key: str) -> Optional[Any]:
    redis = _get_redis()
    if redis:
        try:
            value = redis.get(key)
            if value:
                logger.debug(f"Cache HIT redis key={key}")
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Redis get error key={key}: {e}")

    # In-memory fallback
    if key in _mem_store:
        value, expires_at = _mem_store[key]
        if time.time() < expires_at:
            logger.debug(f"Cache HIT memory key={key}")
            return value
        del _mem_store[key]
    return None


def set(key: str, value: Any, ttl: int = None) -> None:
    ttl = ttl or settings.cache_ttl_seconds

    redis = _get_redis()
    if redis:
        try:
            redis.set(key, json.dumps(value), ex=ttl)
            logger.debug(f"Cache SET redis key={key} ttl={ttl}s")
            return
        except Exception as e:
            logger.warning(f"Redis set error key={key}: {e}")

    # In-memory fallback
    _mem_store[key] = (value, time.time() + ttl)
    logger.debug(f"Cache SET memory key={key} ttl={ttl}s")

    # Cleanup stale entries (simple eviction)
    if len(_mem_store) > 500:
        now = time.time()
        stale = [k for k, (_, exp) in _mem_store.items() if exp < now]
        for k in stale:
            del _mem_store[k]


def delete(key: str) -> None:
    redis = _get_redis()
    if redis:
        try:
            redis.delete(key)
            logger.debug(f"Cache DEL redis key={key}")
        except Exception as e:
            logger.warning(f"Redis delete error key={key}: {e}")

    _mem_store.pop(key, None)


def delete_pattern(pattern: str) -> None:
    """Delete all keys matching a prefix — e.g. 'recommend:user:42:*'"""
    prefix = pattern.rstrip('*')

    redis = _get_redis()
    if redis:
        try:
            # Upstash scan — delete matching keys
            cursor = 0
            while True:
                result = redis.scan(cursor, match=pattern, count=100)
                cursor, keys = result
                if keys:
                    redis.delete(*keys)
                if cursor == 0:
                    break
            logger.debug(f"Cache DEL pattern={pattern}")
        except Exception as e:
            logger.warning(f"Redis scan/delete error pattern={pattern}: {e}")

    # In-memory fallback
    to_del = [k for k in _mem_store if k.startswith(prefix)]
    for k in to_del:
        del _mem_store[k]


def exists(key: str) -> bool:
    redis = _get_redis()
    if redis:
        try:
            return bool(redis.exists(key))
        except Exception:
            pass
    return key in _mem_store and time.time() < _mem_store[key][1]


def get_ttl(key: str) -> Optional[int]:
    """Remaining TTL in seconds."""
    redis = _get_redis()
    if redis:
        try:
            return redis.ttl(key)
        except Exception:
            pass
    if key in _mem_store:
        remaining = int(_mem_store[key][1] - time.time())
        return max(0, remaining)
    return None


# ── Key builders ──────────────────────────────────────────
def make_recommend_key(user_id: int) -> str:
    return f"recommend:user:{user_id}"

def make_recommend_page_key(user_id: int, page: int) -> str:
    return f"recommend:user:{user_id}:page:{page}"

def make_groq_key(user_id: int) -> str:
    return f"groq:user:{user_id}"

def make_user_key(user_id: int) -> str:
    return f"user:profile:{user_id}"

def make_user_pattern(user_id: int) -> str:
    """Pattern to delete ALL cache for a user."""
    return f"*:user:{user_id}*"


# ── Health check ──────────────────────────────────────────
def ping() -> dict:
    redis = _get_redis()
    if not redis:
        return {"backend": "memory", "status": "ok", "keys": len(_mem_store)}
    try:
        redis.ping()
        return {"backend": "redis", "status": "ok"}
    except Exception as e:
        return {"backend": "redis", "status": "error", "error": str(e)}