"""
Traveloka Provider plugin – train search via Traveloka adapter.

File: providers/train/traveloka_provider.py
"""
from providers.base_provider import Provider, NormalizedResult
from utils.logger import logger


class TravelokaProvider(Provider):
    name = "Traveloka"
    travel_type = "train"
    priority = 3

    async def search(self, params: dict) -> list[NormalizedResult]:
        try:
            from providers.train.traveloka_adapter import traveloka_search_trains
            raw = await traveloka_search_trains(
                params.get("origin", ""),
                params.get("destination", ""),
                params.get("date", ""),
                params.get("passengers", 1),
            )
            from services.result_normalizer import normalize_train
            return [normalize_train(r, "Traveloka") for r in raw]
        except Exception as e:
            logger.error(f"[TravelokaProvider] {e}")
            return []
