"""
Pytest conftest – sets up mocks so tests run without live Redis or API keys.

File: tests/conftest.py
"""
import pytest
import asyncio
import os

# Ensure no real external calls are made during tests
os.environ.setdefault("REDIS_URL", "")        # triggers in-memory fallback
os.environ.setdefault("GROQ_API_KEY", "")     # no Groq calls
os.environ.setdefault("OPENAI_API_KEY", "")   # no OpenAI calls


@pytest.fixture(autouse=True)
def patch_redis_pool(monkeypatch):
    """
    Make get_client() always return None → activates in-memory fallbacks
    in search_cache.py and session_manager.py.
    """
    async def _no_redis():
        return None

    monkeypatch.setattr("cache.redis_pool.get_client", _no_redis)
    monkeypatch.setattr("cache.redis_pool.get_pool", _no_redis)


@pytest.fixture(autouse=True)
def clear_mem_caches():
    """Clear in-memory caches between tests to ensure isolation."""
    import cache.search_cache as sc
    import services.session_manager as sm

    sc._mem_cache.clear()
    sm._mem_sessions.clear()
    yield
    sc._mem_cache.clear()
    sm._mem_sessions.clear()
