"""
Amadeus Provider plugin – flight search via Amadeus Flight Offers API.

File: providers/flight/amadeus_provider.py
"""
from providers.base_provider import Provider, NormalizedResult
from utils.logger import logger


class AmadeusProvider(Provider):
    name = "Amadeus"
    travel_type = "flight"
    priority = 1

    async def search(self, params: dict) -> list[NormalizedResult]:
        try:
            from providers.flight.amadeus_adapter import amadeus_search_flights
            raw = await amadeus_search_flights(
                params.get("origin", ""),
                params.get("destination", ""),
                params.get("date", ""),
                params.get("passengers", 1),
            )
            from services.result_normalizer import normalize_flight
            return [normalize_flight(r, "Amadeus") for r in raw]
        except Exception as e:
            logger.error(f"[AmadeusProvider] {e}")
            return []
