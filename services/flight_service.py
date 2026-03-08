"""
Flight Service – orchestrates all flight providers and returns cheapest results.
"""
import asyncio
from utils.logger import logger
from services.price_engine import normalize_and_rank
from providers.flight.amadeus_adapter import amadeus_search_flights
from providers.flight.kiwi_adapter import kiwi_search_flights
from providers.flight.skyscanner_adapter import skyscanner_search_flights


async def search_flight(
    origin: str,
    destination: str,
    date: str,
    adults: int = 1,
    top_n: int = 5,
) -> list[dict]:
    """
    Search flights from Amadeus, Kiwi, and Skyscanner in parallel.

    Returns:
        List of ranked flight results sorted by price.
    """
    logger.info(f"[FlightService] Searching {origin}→{destination} on {date}")

    results_by_provider = await asyncio.gather(
        amadeus_search_flights(origin, destination, date, adults),
        kiwi_search_flights(origin, destination, date, adults),
        skyscanner_search_flights(origin, destination, date, adults),
        return_exceptions=True
    )

    all_results: list[dict] = []
    provider_names = ["Amadeus", "Kiwi", "Skyscanner"]
    for name, result in zip(provider_names, results_by_provider):
        if isinstance(result, Exception):
            logger.error(f"[FlightService] {name} failed: {result}")
        elif isinstance(result, list):
            logger.info(f"[FlightService] {name} returned {len(result)} results")
            all_results.extend(result)

    if not all_results:
        logger.warning("[FlightService] All providers failed – no results")
        return []

    ranked = normalize_and_rank(all_results, travel_type="flight", top_n=top_n)
    logger.info(f"[FlightService] Returning {len(ranked)} ranked results")
    return ranked
