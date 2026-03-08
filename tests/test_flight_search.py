"""
Tests: flight search flow.
Run: pytest tests/test_flight_search.py -v

File: tests/test_flight_search.py
"""
import pytest


def test_resolve_dps():
    from utils.location_resolver import resolve_airport
    assert resolve_airport("bali") == "DPS"
    assert resolve_airport("denpasar") == "DPS"


def test_resolve_cgk():
    from utils.location_resolver import resolve_airport
    assert resolve_airport("jakarta") == "CGK"


@pytest.mark.asyncio
async def test_amadeus_mock():
    from providers.flight.amadeus_adapter import amadeus_search_flights
    results = await amadeus_search_flights("CGK", "DPS", "2026-04-01", 1)
    assert isinstance(results, list)
    if results:
        assert "price" in results[0]


@pytest.mark.asyncio
async def test_flight_cheapest():
    from services.cheapest_engine import run
    mock = [
        {"price": 800000, "currency": "IDR", "airline": "GA", "flight_number": "GA001", "provider": "Amadeus",
         "origin": "CGK", "destination": "DPS", "departure_time": "06:00", "arrival_time": "07:30"},
        {"price": 550000, "currency": "IDR", "airline": "QG", "flight_number": "QG100", "provider": "Kiwi",
         "origin": "CGK", "destination": "DPS", "departure_time": "08:00", "arrival_time": "09:30"},
    ]
    results = run(mock, "flight", top_n=5)
    assert results[0]["price"] <= results[1]["price"]


@pytest.mark.asyncio
async def test_agent_flight_query():
    from agent.openclaw_agent import handle_message
    reply = await handle_message("test_user_002", "pesawat jakarta bali besok")
    assert isinstance(reply, str)
    assert len(reply) > 10
