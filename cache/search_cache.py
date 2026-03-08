"""
Search Cache – thin wrapper around Redis for caching travel search results.

Key pattern:
  train:{ORIGIN}:{DEST}:{DATE}
  flight:{ORIGIN}:{DEST}:{DATE}
  hotel:{CITY}:{CHECK_IN}:{CHECK_OUT}

Default TTL: 10 minutes (600 seconds).

File: cache/search_cache.py
"""
import json
import os
from typing import Any, Optional

from utils.logger import logger

CACHE_TTL = int(os.getenv("CACHE_TTL", "600"))

# In-memory fallback when Redis is unavailable
_mem_cache: dict[str, str] = {}


async def _get_redis():
    """Return Redis client from shared pool, or None if unavailable."""
    from cache.redis_pool import get_client
    return await get_client()


# ─── Key builders ─────────────────────────────────────────────────────────────

def train_key(origin: str, destination: str, date: str) -> str:
    return f"train:{origin.upper()}:{destination.upper()}:{date}"


def flight_key(origin: str, destination: str, date: str) -> str:
    return f"flight:{origin.upper()}:{destination.upper()}:{date}"


def hotel_key(city: str, check_in: str, check_out: str) -> str:
    return f"hotel:{city.upper()}:{check_in}:{check_out}"


# ─── Core ops ─────────────────────────────────────────────────────────────────

async def get(key: str) -> Optional[Any]:
    """Return cached value or None on miss/error."""
    try:
        r = await _get_redis()
        if r is None:
            raw = _mem_cache.get(key)
        else:
            raw = await r.get(key)
        if raw is None:
            logger.debug(f"[SearchCache] MISS {key}")
            return None
        logger.debug(f"[SearchCache] HIT  {key}")
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"[SearchCache] GET error ({key}): {e}")
        return None


async def set(key: str, value: Any, ttl: int = CACHE_TTL) -> bool:
    """Store JSON-serialisable value with TTL. Returns True on success."""
    try:
        r = await _get_redis()
        serialized = json.dumps(value, default=str)
        if r is None:
            _mem_cache[key] = serialized
        else:
            await r.setex(key, ttl, serialized)
        logger.debug(f"[SearchCache] SET  {key} TTL={ttl}s")
        return True
    except Exception as e:
        logger.warning(f"[SearchCache] SET error ({key}): {e}")
        return False


async def delete(key: str) -> bool:
    try:
        r = await _get_redis()
        await r.delete(key)
        return True
    except Exception as e:
        logger.warning(f"[SearchCache] DEL error ({key}): {e}")
        return False


async def exists(key: str) -> bool:
    try:
        r = await _get_redis()
        return bool(await r.exists(key))
    except Exception:
        return False


# ─── Convenience wrappers ─────────────────────────────────────────────────────

async def get_train(origin: str, dest: str, date: str) -> Optional[list]:
    return await get(train_key(origin, dest, date))


async def set_train(origin: str, dest: str, date: str, results: list, ttl: int = CACHE_TTL):
    await set(train_key(origin, dest, date), results, ttl)


async def get_flight(origin: str, dest: str, date: str) -> Optional[list]:
    return await get(flight_key(origin, dest, date))


async def set_flight(origin: str, dest: str, date: str, results: list, ttl: int = CACHE_TTL):
    await set(flight_key(origin, dest, date), results, ttl)


async def get_hotel(city: str, check_in: str, check_out: str) -> Optional[list]:
    return await get(hotel_key(city, check_in, check_out))


async def set_hotel(city: str, check_in: str, check_out: str, results: list, ttl: int = CACHE_TTL):
    await set(hotel_key(city, check_in, check_out), results, ttl)
