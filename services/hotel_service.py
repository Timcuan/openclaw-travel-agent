"""
Hotel Service – orchestrates all hotel providers and returns cheapest results,
optionally also sorting by rating.
"""
import asyncio
from utils.logger import logger
from services.price_engine import normalize_and_rank
from providers.hotel.liteapi_adapter import liteapi_search_hotels
from providers.hotel.booking_adapter import booking_search_hotels
from providers.hotel.agoda_scraper import agoda_search_hotels


async def search_hotel(
    city: str,
    check_in: str,
    check_out: str,
    adults: int = 2,
    rooms: int = 1,
    top_n: int = 5,
) -> list[dict]:
    """
    Search hotels from LiteAPI, Booking.com, and Agoda in parallel.

    Returns:
        List of ranked hotel results sorted primarily by price.
    """
    logger.info(f"[HotelService] Searching {city} {check_in}→{check_out}")

    results_by_provider = await asyncio.gather(
        liteapi_search_hotels(city, check_in, check_out, adults, rooms),
        booking_search_hotels(city, check_in, check_out, adults, rooms),
        agoda_search_hotels(city, check_in, check_out, adults, rooms),
        return_exceptions=True
    )

    all_results: list[dict] = []
    provider_names = ["LiteAPI", "Booking.com", "Agoda"]
    for name, result in zip(provider_names, results_by_provider):
        if isinstance(result, Exception):
            logger.error(f"[HotelService] {name} failed: {result}")
        elif isinstance(result, list):
            logger.info(f"[HotelService] {name} returned {len(result)} results")
            all_results.extend(result)

    if not all_results:
        logger.warning("[HotelService] All providers failed – no results")
        return []

    ranked = normalize_and_rank(all_results, travel_type="hotel", top_n=top_n)
    logger.info(f"[HotelService] Returning {len(ranked)} ranked results")
    return ranked
