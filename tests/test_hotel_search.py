"""
Tests: hotel search flow.
Run: pytest tests/test_hotel_search.py -v

File: tests/test_hotel_search.py
"""
import pytest


def test_resolve_hotel_city():
    from utils.location_resolver import resolve_hotel_city
    assert resolve_hotel_city("jogja") == "Yogyakarta"
    assert resolve_hotel_city("bali") == "Bali"
    assert resolve_hotel_city("sby") == "Surabaya"


@pytest.mark.asyncio
async def test_liteapi_mock():
    from providers.hotel.liteapi_adapter import liteapi_search_hotels
    results = await liteapi_search_hotels("Bali", "2026-04-01", "2026-04-02", 2, 1)
    assert isinstance(results, list)


def test_hotel_cheapest():
    from services.cheapest_engine import run
    mock = [
        {"price_per_night": 900000, "currency": "IDR", "hotel_name": "Luxury", "provider": "LiteAPI",
         "city": "Bali", "check_in": "2026-04-01", "check_out": "2026-04-02", "star_rating": 5},
        {"price_per_night": 320000, "currency": "IDR", "hotel_name": "Budget", "provider": "Agoda",
         "city": "Bali", "check_in": "2026-04-01", "check_out": "2026-04-02", "star_rating": 2},
    ]
    results = run(mock, "hotel", top_n=5)
    assert results[0]["rank"] == 1
    assert results[0].get("price_per_night") or results[0].get("price") > 0


@pytest.mark.asyncio
async def test_agent_hotel_query():
    from agent.openclaw_agent import handle_message
    reply = await handle_message("test_user_003", "hotel murah bandung 2 malam")
    assert isinstance(reply, str)
    assert len(reply) > 10


@pytest.mark.asyncio
async def test_trip_planning():
    from agent.openclaw_agent import handle_message
    reply = await handle_message("test_user_004", "trip ke bandung akhir pekan ini")
    assert isinstance(reply, str)
    assert "Bandung" in reply or "bandung" in reply.lower()
