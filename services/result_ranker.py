"""
Result Ranker – multi-factor scoring engine.

Ranking formula (configurable weights):

  score = (price_weight  * price_score)
        + (duration_weight * duration_score)
        + (provider_weight * provider_score)

All scores are normalised to [0, 1] so weights are comparable.
Lower score = better (like golf: lower is better).

Default weights:
  price    : 0.60  (most important for budget travel)
  duration : 0.25
  provider : 0.15

File: services/result_ranker.py
"""
from typing import Literal
from utils.logger import logger

TravelType = Literal["train", "flight", "hotel"]

# Provider trust scores (lower = more trusted)
PROVIDER_SCORES = {
    # Train
    "KAI": 0.0,
    "Tiket": 0.1,
    "Traveloka": 0.2,
    # Flight
    "Amadeus": 0.0,
    "Kiwi": 0.15,
    "Skyscanner": 0.25,
    # Hotel
    "LiteAPI": 0.0,
    "Booking.com": 0.1,
    "Agoda": 0.15,
}

DEFAULT_WEIGHTS = {
    "price": 0.60,
    "duration": 0.25,
    "provider": 0.15,
}


def rank(
    results: list[dict],
    travel_type: TravelType,
    top_n: int = 5,
    weights: dict | None = None,
) -> list[dict]:
    """
    Score and rank results using multi-factor formula.

    Args:
        results: Raw merged results (with 'price' in IDR already normalised).
        travel_type: 'train' | 'flight' | 'hotel'.
        top_n: Max results to return.
        weights: Optional weight overrides {'price': float, 'duration': float, 'provider': float}.

    Returns:
        Sorted list with 'rank' and 'score' fields attached.
    """
    if not results:
        return []

    w = {**DEFAULT_WEIGHTS, **(weights or {})}

    # Extract metric arrays for normalisation
    prices = [_price(r) for r in results]
    durations = [_duration_minutes(r) for r in results]

    p_min, p_max = min(prices), max(prices)
    d_min, d_max = min(durations), max(durations)

    scored = []
    for r in results:
        p_score = _normalise(_price(r), p_min, p_max)
        d_score = _normalise(_duration_minutes(r), d_min, d_max)
        prov_score = PROVIDER_SCORES.get(r.get("provider", ""), 0.2)

        score = (
            w["price"]    * p_score
            + w["duration"] * d_score
            + w["provider"] * prov_score
        )
        r["_score"] = round(score, 4)
        scored.append(r)

    # Sort ascending (lower score = better)
    scored.sort(key=lambda r: (r["_score"], _price(r)))

    top = scored[:top_n]
    for i, r in enumerate(top, start=1):
        r["rank"] = i

    if top:
        logger.info(
            f"[Ranker] {travel_type}: ranked {len(scored)} → top {len(top)} | "
            f"best score={top[0]['_score']:.3f} Rp{_price(top[0]):,.0f}"
        )

    return top


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _price(r: dict) -> float:
    return float(r.get("price_idr") or r.get("price") or r.get("price_per_night") or 999_999_999)


def _duration_minutes(r: dict) -> float:
    """Convert duration string or None to minutes."""
    raw = r.get("duration") or ""
    if not raw:
        return 120.0  # default fallback

    import re
    total = 0
    h = re.search(r"(\d+)\s*[jJhH]", raw)
    m = re.search(r"(\d+)\s*[mM]", raw)
    if h:
        total += int(h.group(1)) * 60
    if m:
        total += int(m.group(1))
    return float(total) if total else 120.0


def _normalise(value: float, low: float, high: float) -> float:
    """Min-max normalise to [0, 1]. Returns 0 if range is zero."""
    if high == low:
        return 0.0
    return (value - low) / (high - low)
