"""
Provider Aggregator – unified engine that calls all providers for a given
travel type, merges results, and returns them ready for cheapest_engine.

Priority order respected:
  Train  → KAI (1st), Tiket (2nd), Traveloka (3rd)
  Flight → Amadeus (1st), Kiwi (2nd), Skyscanner (3rd)
  Hotel  → LiteAPI (1st), Booking (2nd), Agoda (3rd)

File: services/provider_aggregator.py
"""
import asyncio
from typing import Literal
from utils.logger import logger
from utils.location_resolver import resolve_train_station, resolve_airport, resolve_hotel_city

# Train providers
from providers.train.kai_scraper import kai_search_trains
from providers.train.tiket_adapter import tiket_search_trains
from providers.train.traveloka_adapter import traveloka_search_trains

# Flight providers
from providers.flight.amadeus_adapter import amadeus_search_flights
from providers.flight.kiwi_adapter import kiwi_search_flights
from providers.flight.skyscanner_adapter import skyscanner_search_flights

# Hotel providers
from providers.hotel.liteapi_adapter import liteapi_search_hotels
from providers.hotel.booking_adapter import booking_search_hotels
from providers.hotel.agoda_scraper import agoda_search_hotels


TravelType = Literal["train", "flight", "hotel"]


async def aggregate_train(
    origin: str,
    destination: str,
    date: str,
    passengers: int = 1,
) -> list[dict]:
    """
    Call all train providers in parallel (priority: KAI > Tiket > Traveloka).
    Returns merged, un-ranked raw results.
    """
    origin_code = resolve_train_station(origin) or origin.upper()
    dest_code = resolve_train_station(destination) or destination.upper()

    logger.info(f"[Aggregator] Train {origin_code}→{dest_code} {date} ×{passengers}")

    results_raw = await asyncio.gather(
        kai_search_trains(origin_code, dest_code, date, passengers),
        tiket_search_trains(origin_code, dest_code, date, passengers),
        traveloka_search_trains(origin_code, dest_code, date, passengers),
        return_exceptions=True,
    )

    return _merge("train", results_raw, ["KAI", "Tiket", "Traveloka"])


async def aggregate_flight(
    origin: str,
    destination: str,
    date: str,
    passengers: int = 1,
) -> list[dict]:
    """
    Call all flight providers in parallel (priority: Amadeus > Kiwi > Skyscanner).
    Returns merged, un-ranked raw results.
    """
    origin_iata = resolve_airport(origin) or origin.upper()
    dest_iata = resolve_airport(destination) or destination.upper()

    logger.info(f"[Aggregator] Flight {origin_iata}→{dest_iata} {date} ×{passengers}")

    results_raw = await asyncio.gather(
        amadeus_search_flights(origin_iata, dest_iata, date, passengers),
        kiwi_search_flights(origin_iata, dest_iata, date, passengers),
        skyscanner_search_flights(origin_iata, dest_iata, date, passengers),
        return_exceptions=True,
    )

    return _merge("flight", results_raw, ["Amadeus", "Kiwi", "Skyscanner"])


async def aggregate_hotel(
    city: str,
    check_in: str,
    check_out: str,
    adults: int = 2,
    rooms: int = 1,
) -> list[dict]:
    """
    Call all hotel providers in parallel (priority: LiteAPI > Booking > Agoda).
    Returns merged, un-ranked raw results.
    """
    canonical_city = resolve_hotel_city(city)

    logger.info(f"[Aggregator] Hotel {canonical_city} {check_in}→{check_out} ×{adults}")

    results_raw = await asyncio.gather(
        liteapi_search_hotels(canonical_city, check_in, check_out, adults, rooms),
        booking_search_hotels(canonical_city, check_in, check_out, adults, rooms),
        agoda_search_hotels(canonical_city, check_in, check_out, adults, rooms),
        return_exceptions=True,
    )

    return _merge("hotel", results_raw, ["LiteAPI", "Booking.com", "Agoda"])


def _merge(
    travel_type: str,
    results_raw: tuple,
    provider_names: list[str],
) -> list[dict]:
    """Merge results from multiple providers, log errors, tag with provider priority."""
    all_results: list[dict] = []
    for priority, (name, result) in enumerate(zip(provider_names, results_raw), start=1):
        if isinstance(result, Exception):
            logger.error(f"[Aggregator] {name} error: {result}")
        elif isinstance(result, list):
            for r in result:
                r["_priority"] = priority  # used for de-dup tie-breaking
                all_results.append(r)
            logger.info(f"[Aggregator] {name} → {len(result)} results")
        else:
            logger.warning(f"[Aggregator] {name} returned unexpected type: {type(result)}")

    logger.info(f"[Aggregator] Total merged ({travel_type}): {len(all_results)}")
    return all_results
