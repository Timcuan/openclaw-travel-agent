"""
Train Service – orchestrates all train providers and returns cheapest results.

Calls KAI scraper, Tiket adapter, and Traveloka adapter in parallel,
then ranks by price using the price engine.
"""
import asyncio
from utils.logger import logger
from services.price_engine import normalize_and_rank
from providers.train.kai_scraper import kai_search_trains
from providers.train.tiket_adapter import tiket_search_trains
from providers.train.traveloka_adapter import traveloka_search_trains


async def search_train(
    origin: str,
    destination: str,
    date: str,
    adult: int = 1,
    top_n: int = 5,
) -> list[dict]:
    """
    Search trains from all providers in parallel and return cheapest results.

    Args:
        origin: City or station code.
        destination: City or station code.
        date: YYYY-MM-DD.
        adult: Number of adult passengers.
        top_n: Max results to return.

    Returns:
        List of ranked train results.
    """
    logger.info(f"[TrainService] Searching {origin}→{destination} on {date}")

    # Call all 3 providers concurrently
    kai_task = kai_search_trains(origin, destination, date, adult)
    tiket_task = tiket_search_trains(origin, destination, date, adult)
    traveloka_task = traveloka_search_trains(origin, destination, date, adult)

    results_by_provider = await asyncio.gather(
        kai_task, tiket_task, traveloka_task,
        return_exceptions=True
    )

    # Merge results, skip provider failures
    all_results: list[dict] = []
    provider_names = ["KAI", "Tiket", "Traveloka"]
    for name, result in zip(provider_names, results_by_provider):
        if isinstance(result, Exception):
            logger.error(f"[TrainService] {name} failed: {result}")
        elif isinstance(result, list):
            logger.info(f"[TrainService] {name} returned {len(result)} results")
            all_results.extend(result)

    if not all_results:
        logger.warning("[TrainService] All providers failed – no results")
        return []

    ranked = normalize_and_rank(all_results, travel_type="train", top_n=top_n)
    logger.info(f"[TrainService] Returning {len(ranked)} ranked results")
    return ranked
