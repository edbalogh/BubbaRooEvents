"""Redis caching layer for hot data.

Provides caching for frequently accessed data like event searches,
recommendation results, and popularity scores to reduce DB load.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    """Get or create the Redis connection pool."""
    global _pool
    if _pool is None:
        _pool = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
        )
    return _pool


async def cache_get(key: str) -> Any | None:
    """Get a value from cache. Returns None on miss or error."""
    try:
        r = await get_redis()
        value = await r.get(key)
        if value is not None:
            return json.loads(value)
    except Exception as e:
        logger.debug(f"Cache get failed for {key}: {e}")
    return None


async def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    """Set a value in cache with TTL."""
    try:
        r = await get_redis()
        await r.setex(key, ttl_seconds, json.dumps(value, default=str))
    except Exception as e:
        logger.debug(f"Cache set failed for {key}: {e}")


async def cache_delete(key: str) -> None:
    """Delete a value from cache."""
    try:
        r = await get_redis()
        await r.delete(key)
    except Exception as e:
        logger.debug(f"Cache delete failed for {key}: {e}")


async def cache_delete_pattern(pattern: str) -> None:
    """Delete all keys matching a pattern."""
    try:
        r = await get_redis()
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match=pattern, count=100)
            if keys:
                await r.delete(*keys)
            if cursor == 0:
                break
    except Exception as e:
        logger.debug(f"Cache pattern delete failed for {pattern}: {e}")


# --- Typed cache helpers ---


CACHE_TTL_EVENT_SEARCH = 180  # 3 minutes
CACHE_TTL_RECOMMENDATIONS = 300  # 5 minutes
CACHE_TTL_POPULARITY = 600  # 10 minutes
CACHE_TTL_TONIGHT = 120  # 2 minutes
CACHE_TTL_CATEGORIES = 3600  # 1 hour


def event_search_key(city: str, params_hash: str) -> str:
    return f"events:search:{city.lower()}:{params_hash}"


def recommendations_key(user_id: str, city: str) -> str:
    return f"recs:{user_id}:{city.lower()}"


def tonight_key(city: str) -> str:
    return f"events:tonight:{city.lower()}"


def popularity_key() -> str:
    return "events:popularity"


def categories_key() -> str:
    return "categories:all"


async def invalidate_user_recommendations(user_id: str) -> None:
    """Invalidate recommendation cache when user preferences change."""
    await cache_delete_pattern(f"recs:{user_id}:*")


async def invalidate_event_caches(city: str | None = None) -> None:
    """Invalidate event caches after ingestion."""
    if city:
        await cache_delete_pattern(f"events:*:{city.lower()}:*")
        await cache_delete_pattern(f"events:tonight:{city.lower()}")
    else:
        await cache_delete_pattern("events:*")
    await cache_delete(popularity_key())
