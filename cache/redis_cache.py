"""
Redis cache helpers.

Key pattern: {travel_type}:{origin}:{destination}:{date}
TTL: 10 minutes (600 seconds)
"""
import json
import os
from typing import Any, Optional

import redis.asyncio as aioredis
from utils.logger import logger

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", "600"))

# Singleton pool
_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = await aioredis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def cache_get(key: str) -> Optional[Any]:
    """Return cached value or None."""
    try:
        client = await get_redis()
        raw = await client.get(key)
        if raw is None:
            return None
        logger.debug(f"Cache HIT: {key}")
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Cache GET error for {key}: {e}")
        return None


async def cache_set(key: str, value: Any, ttl: int = CACHE_TTL) -> bool:
    """Store a JSON-serialisable value with TTL."""
    try:
        client = await get_redis()
        await client.setex(key, ttl, json.dumps(value, default=str))
        logger.debug(f"Cache SET: {key} (TTL={ttl}s)")
        return True
    except Exception as e:
        logger.warning(f"Cache SET error for {key}: {e}")
        return False


async def cache_delete(key: str) -> bool:
    """Delete a cache key."""
    try:
        client = await get_redis()
        await client.delete(key)
        return True
    except Exception as e:
        logger.warning(f"Cache DELETE error for {key}: {e}")
        return False


def build_train_key(origin: str, destination: str, date: str) -> str:
    return f"train:{origin.upper()}:{destination.upper()}:{date}"


def build_flight_key(origin: str, destination: str, date: str) -> str:
    return f"flight:{origin.upper()}:{destination.upper()}:{date}"


def build_hotel_key(city: str, check_in: str, check_out: str) -> str:
    return f"hotel:{city.upper()}:{check_in}:{check_out}"


async def close_redis():
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
