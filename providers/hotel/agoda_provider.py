"""Agoda Hotel Provider plugin (Playwright scraper). File: providers/hotel/agoda_provider.py"""
from providers.base_provider import Provider, NormalizedResult
from utils.logger import logger


class AgodaProvider(Provider):
    name = "Agoda"
    travel_type = "hotel"
    priority = 3

    async def search(self, params: dict) -> list[NormalizedResult]:
        try:
            from providers.hotel.agoda_scraper import agoda_search_hotels
            raw = await agoda_search_hotels(
                params.get("city", ""), params.get("check_in", ""),
                params.get("check_out", ""), params.get("adults", 2), params.get("rooms", 1),
            )
            from services.result_normalizer import normalize_hotel
            return [normalize_hotel(r, "Agoda") for r in raw]
        except Exception as e:
            logger.error(f"[AgodaProvider] {e}")
            return []
