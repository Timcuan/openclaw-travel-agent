"""Kiwi Provider plugin. File: providers/flight/kiwi_provider.py"""
from providers.base_provider import Provider, NormalizedResult
from utils.logger import logger


class KiwiProvider(Provider):
    name = "Kiwi"
    travel_type = "flight"
    priority = 2

    async def search(self, params: dict) -> list[NormalizedResult]:
        try:
            from providers.flight.kiwi_adapter import kiwi_search_flights
            raw = await kiwi_search_flights(
                params.get("origin", ""), params.get("destination", ""),
                params.get("date", ""), params.get("passengers", 1),
            )
            from services.result_normalizer import normalize_flight
            return [normalize_flight(r, "Kiwi") for r in raw]
        except Exception as e:
            logger.error(f"[KiwiProvider] {e}")
            return []
