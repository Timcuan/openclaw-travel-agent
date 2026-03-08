"""LiteAPI Hotel Provider plugin. File: providers/hotel/liteapi_provider.py"""
from providers.base_provider import Provider, NormalizedResult
from utils.logger import logger


class LiteAPIProvider(Provider):
    name = "LiteAPI"
    travel_type = "hotel"
    priority = 1

    async def search(self, params: dict) -> list[NormalizedResult]:
        try:
            from providers.hotel.liteapi_adapter import liteapi_search_hotels
            raw = await liteapi_search_hotels(
                params.get("city", ""), params.get("check_in", ""),
                params.get("check_out", ""), params.get("adults", 2), params.get("rooms", 1),
            )
            from services.result_normalizer import normalize_hotel
            return [normalize_hotel(r, "LiteAPI") for r in raw]
        except Exception as e:
            logger.error(f"[LiteAPIProvider] {e}")
            return []
