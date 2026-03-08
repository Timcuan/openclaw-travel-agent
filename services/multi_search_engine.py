"""
Multi Search Engine – single entry point that searches all providers
for the requested travel type, with failsafe per-provider catching.

Features:
- asyncio.gather for true parallel execution
- Per-provider exception isolation (never crashes the bot)
- Fallback chain: if primary provider fails, uses its mock data automatically
- Returns raw merged results for cheapest_engine / result_ranker

File: services/multi_search_engine.py
"""
import asyncio
import time
from typing import Literal
from utils.logger import logger
from utils.location_resolver import (
    resolve_train_station,
    resolve_airport,
    resolve_hotel_city,
)

TravelType = Literal["train", "flight", "hotel"]


async def search(
    travel_type: TravelType,
    *,
    origin: str = "",
    destination: str = "",
    date: str = "",
    city: str = "",
    check_in: str = "",
    check_out: str = "",
    passengers: int = 1,
    rooms: int = 1,
) -> dict:
    """
    Unified search entry point.

    Returns:
        {
            "results": [list of raw provider results],
            "travel_type": str,
            "providers_called": [list of provider names],
            "providers_failed": [list of failed names],
            "duration_ms": int,
        }
    """
    t0 = time.monotonic()

    if travel_type == "train":
        results, called, failed = await _search_train(origin, destination, date, passengers)
    elif travel_type == "flight":
        results, called, failed = await _search_flight(origin, destination, date, passengers)
    elif travel_type == "hotel":
        results, called, failed = await _search_hotel(city, check_in, check_out, passengers, rooms)
    else:
        results, called, failed = [], [], []

    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        f"[MultiSearch] {travel_type} → {len(results)} results "
        f"in {duration_ms}ms | ok={called} fail={failed}"
    )

    return {
        "results": results,
        "travel_type": travel_type,
        "providers_called": called,
        "providers_failed": failed,
        "duration_ms": duration_ms,
    }


# ─── Train ────────────────────────────────────────────────────────────────────

async def _search_train(origin, destination, date, passengers):
    from providers.train.kai_scraper import kai_search_trains
    from providers.train.tiket_adapter import tiket_search_trains
    from providers.train.traveloka_adapter import traveloka_search_trains

    o = resolve_train_station(origin) or origin.upper()
    d = resolve_train_station(destination) or destination.upper()

    tasks = {
        "KAI":       kai_search_trains(o, d, date, passengers),
        "Tiket":     tiket_search_trains(o, d, date, passengers),
        "Traveloka": traveloka_search_trains(o, d, date, passengers),
    }
    return await _run_tasks(tasks)


# ─── Flight ───────────────────────────────────────────────────────────────────

async def _search_flight(origin, destination, date, passengers):
    from providers.flight.amadeus_adapter import amadeus_search_flights
    from providers.flight.kiwi_adapter import kiwi_search_flights
    from providers.flight.skyscanner_adapter import skyscanner_search_flights

    o = resolve_airport(origin) or origin.upper()
    d = resolve_airport(destination) or destination.upper()

    tasks = {
        "Amadeus":    amadeus_search_flights(o, d, date, passengers),
        "Kiwi":       kiwi_search_flights(o, d, date, passengers),
        "Skyscanner": skyscanner_search_flights(o, d, date, passengers),
    }
    return await _run_tasks(tasks)


# ─── Hotel ────────────────────────────────────────────────────────────────────

async def _search_hotel(city, check_in, check_out, adults, rooms):
    from providers.hotel.liteapi_adapter import liteapi_search_hotels
    from providers.hotel.booking_adapter import booking_search_hotels
    from providers.hotel.agoda_scraper import agoda_search_hotels

    c = resolve_hotel_city(city)

    tasks = {
        "LiteAPI":     liteapi_search_hotels(c, check_in, check_out, adults, rooms),
        "Booking.com": booking_search_hotels(c, check_in, check_out, adults, rooms),
        "Agoda":       agoda_search_hotels(c, check_in, check_out, adults, rooms),
    }
    return await _run_tasks(tasks)


# ─── Shared executor ──────────────────────────────────────────────────────────

async def _run_tasks(tasks: dict) -> tuple[list, list, list]:
    """
    Run all provider coroutines concurrently with individual exception handling.
    Returns (all_results, called_names, failed_names).
    """
    names = list(tasks.keys())
    coros = list(tasks.values())

    raw = await asyncio.gather(*coros, return_exceptions=True)

    all_results: list[dict] = []
    called: list[str] = []
    failed: list[str] = []

    for name, result in zip(names, raw):
        if isinstance(result, Exception):
            logger.error(f"[MultiSearch] {name} exception: {result}")
            failed.append(name)
        elif isinstance(result, list):
            called.append(name)
            for r in result:
                r["_source_provider"] = name
            all_results.extend(result)
            logger.debug(f"[MultiSearch] {name}: {len(result)} results")
        else:
            logger.warning(f"[MultiSearch] {name}: unexpected return type {type(result)}")
            failed.append(name)

    return all_results, called, failed
