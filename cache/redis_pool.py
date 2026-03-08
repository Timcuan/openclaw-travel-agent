"""
Shared Redis connection pool – single pool for the whole process.

Both search_cache.py and session_manager.py import from here instead of
creating their own pools. This prevents connection exhaustion.

File: cache/redis_pool.py
"""
import os
from typing import Optional
from utils.logger import logger

_pool = None

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


async def get_pool():
    """
    Return the shared Redis connection pool.
    Creates it on first call (lazy singleton).
    Returns None if Redis is unavailable (fallback to in-memory).
    """
    global _pool
    if _pool is not None:
        return _pool

    try:
        import redis.asyncio as aioredis
        _pool = aioredis.ConnectionPool.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=10,
        )
        # Verify connection
        client = aioredis.Redis(connection_pool=_pool)
        await client.ping()
        logger.info(f"[Redis] Pool connected → {REDIS_URL}")
    except Exception as e:
        logger.warning(f"[Redis] Not available ({e}) – using in-memory fallback")
        _pool = None

    return _pool


async def get_client():
    """
    Return an async Redis client from the shared pool.
    Returns None if Redis is unavailable.
    """
    pool = await get_pool()
    if pool is None:
        return None
    import redis.asyncio as aioredis
    return aioredis.Redis(connection_pool=pool)


async def close_pool():
    """Call on application shutdown to release connections cleanly."""
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None
        logger.info("[Redis] Pool disconnected")
