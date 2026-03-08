"""
KAI Provider plugin – train search via Playwright scraper with mock fallback.
Implements Provider interface.

File: providers/train/kai_provider.py
"""
from providers.base_provider import Provider, NormalizedResult
from utils.logger import logger


class KAIProvider(Provider):
    name = "KAI"
    travel_type = "train"
    priority = 1

    async def search(self, params: dict) -> list[NormalizedResult]:
        try:
            from providers.train.kai_scraper import kai_search_trains
            raw = await kai_search_trains(
                params.get("origin", ""),
                params.get("destination", ""),
                params.get("date", ""),
                params.get("passengers", 1),
            )
            return [_to_norm(r) for r in raw]
        except Exception as e:
            logger.error(f"[KAIProvider] {e}")
            return []


def _to_norm(r: dict) -> NormalizedResult:
    from services.result_normalizer import normalize_train
    return normalize_train(r, "KAI")
