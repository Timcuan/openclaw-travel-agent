"""Skyscanner Provider plugin. File: providers/flight/skyscanner_provider.py"""
from providers.base_provider import Provider, NormalizedResult
from utils.logger import logger


class SkyscannerProvider(Provider):
    name = "Skyscanner"
    travel_type = "flight"
    priority = 3

    async def search(self, params: dict) -> list[NormalizedResult]:
        try:
            from providers.flight.skyscanner_adapter import skyscanner_search_flights
            raw = await skyscanner_search_flights(
                params.get("origin", ""), params.get("destination", ""),
                params.get("date", ""), params.get("passengers", 1),
            )
            from services.result_normalizer import normalize_flight
            return [normalize_flight(r, "Skyscanner") for r in raw]
        except Exception as e:
            logger.error(f"[SkyscannerProvider] {e}")
            return []
