"""
Session Manager – Redis-backed conversation state per user.

Tracks the booking flow state machine:
  idle              → fresh / no active search
  results_shown     → search results displayed, awaiting selection
  awaiting_name     → user selected option, bot asking for passenger name
  awaiting_payment  → name collected, bot asking for payment method
  complete          → booking finalised

State schema (stored as Redis hash):
  stage             : string (state name above)
  travel_type       : train | flight | hotel
  selected_option   : int (1-based rank)
  last_results_key  : cache key to retrieve last search results
  passenger_name    : string
  payment_method    : string

File: services/session_manager.py
"""
import json
import os
from typing import Any, Optional

from utils.logger import logger

SESSION_TTL = 3600  # 1 hour

# In-memory fallback when Redis is unavailable
_mem_sessions: dict[str, str] = {}


async def _get_redis():
    """Return Redis client from shared pool, or None if unavailable."""
    from cache.redis_pool import get_client
    return await get_client()


def _session_key(user_id: str) -> str:
    return f"session:{user_id}"


# ─── Public API ───────────────────────────────────────────────────────────────

async def get_session(user_id: str) -> dict:
    """
    Return the current session dict for a user.
    Returns a default 'idle' session if none exists.
    """
    r = await _get_redis()
    key = _session_key(user_id)
    try:
        raw = await r.get(key) if r else _mem_sessions.get(key)
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.warning(f"[Session] GET error for {user_id}: {e}")
    return _default_session()


async def save_session(user_id: str, session: dict) -> None:
    """Persist session dict to Redis (or memory) with TTL."""
    r = await _get_redis()
    key = _session_key(user_id)
    serialized = json.dumps(session, default=str)
    try:
        if r:
            await r.setex(key, SESSION_TTL, serialized)
        else:
            _mem_sessions[key] = serialized
    except Exception as e:
        logger.warning(f"[Session] SAVE error for {user_id}: {e}")
        _mem_sessions[key] = serialized  # fallback to memory on Redis write failure


async def update_session(user_id: str, **kwargs) -> dict:
    """Load, update specific fields, and save session."""
    session = await get_session(user_id)
    session.update(kwargs)
    await save_session(user_id, session)
    return session


async def reset_session(user_id: str) -> None:
    """Clear session back to idle state."""
    r = await _get_redis()
    key = _session_key(user_id)
    try:
        if r:
            await r.delete(key)
        _mem_sessions.pop(key, None)
    except Exception as e:
        logger.warning(f"[Session] RESET error for {user_id}: {e}")
        _mem_sessions.pop(key, None)
    logger.debug(f"[Session] Reset for user={user_id}")


async def set_stage(user_id: str, stage: str) -> None:
    await update_session(user_id, stage=stage)


async def get_stage(user_id: str) -> str:
    session = await get_session(user_id)
    return session.get("stage", "idle")


async def store_results(user_id: str, travel_type: str, results: list[dict]) -> None:
    """Cache the last search results inside the session."""
    await update_session(
        user_id,
        stage="results_shown",
        travel_type=travel_type,
        last_results=results,
    )


async def get_results(user_id: str) -> tuple[str, list[dict]]:
    """Return (travel_type, results) from session."""
    session = await get_session(user_id)
    return session.get("travel_type", ""), session.get("last_results", [])


async def get_selected_offer(user_id: str, option_n: int) -> Optional[dict]:
    """Return the offer dict for rank=option_n from last results."""
    _, results = await get_results(user_id)
    for r in results:
        if r.get("rank") == option_n:
            return r
    return None


def _default_session() -> dict:
    return {
        "stage": "idle",
        "travel_type": None,
        "selected_option": None,
        "last_results": [],
        "passenger_name": None,
        "payment_method": None,
        "selected_offer": None,
    }
