"""
Tiket Provider plugin – train search via Tiket.com adapter.

File: providers/train/tiket_provider.py
"""
from providers.base_provider import Provider, NormalizedResult
from utils.logger import logger


class TiketProvider(Provider):
    name = "Tiket"
    travel_type = "train"
    priority = 2

    async def search(self, params: dict) -> list[NormalizedResult]:
        try:
            from providers.train.tiket_adapter import tiket_search_trains
            raw = await tiket_search_trains(
                params.get("origin", ""),
                params.get("destination", ""),
                params.get("date", ""),
                params.get("passengers", 1),
            )
            from services.result_normalizer import normalize_train
            return [normalize_train(r, "Tiket") for r in raw]
        except Exception as e:
            logger.error(f"[TiketProvider] {e}")
            return []
