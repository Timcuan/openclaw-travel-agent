"""
Deal Detector – flags abnormally cheap prices as 🔥 BEST DEAL.

Logic:
  if price < route_average * DEAL_THRESHOLD → tag as deal

Route averages are seeded from historical data below.
New averages are learned per-session from search results.

File: services/deal_detector.py
"""
from utils.logger import logger

DEAL_THRESHOLD = 0.70   # price < 70% of average → BEST DEAL
GOOD_THRESHOLD = 0.85   # price < 85% → GOOD PRICE

# ─── Baseline route average prices (IDR) – seeded from public data ────────────

_TRAIN_AVERAGES: dict[tuple[str, str], float] = {
    ("GMR", "SBI"): 520_000,   ("SBI", "GMR"): 520_000,
    ("GMR", "YK"):  380_000,   ("YK",  "GMR"): 380_000,
    ("GMR", "SLO"): 400_000,   ("SLO", "GMR"): 400_000,
    ("GMR", "SMC"): 300_000,   ("SMC", "GMR"): 300_000,
    ("GMR", "BD"):  150_000,   ("BD",  "GMR"): 150_000,
    ("SBI", "MLG"): 60_000,    ("MLG", "SBI"): 60_000,
    ("SBI", "YK"):  280_000,   ("YK",  "SBI"): 280_000,
}

_FLIGHT_AVERAGES: dict[tuple[str, str], float] = {
    ("CGK", "DPS"): 700_000,   ("DPS", "CGK"): 700_000,
    ("CGK", "SUB"): 620_000,   ("SUB", "CGK"): 620_000,
    ("CGK", "UPG"): 850_000,   ("UPG", "CGK"): 850_000,
    ("CGK", "MES"): 900_000,   ("MES", "CGK"): 900_000,
    ("SUB", "DPS"): 450_000,   ("DPS", "SUB"): 450_000,
    ("CGK", "BPN"): 950_000,   ("BPN", "CGK"): 950_000,
}

_HOTEL_AVERAGES: dict[str, float] = {
    "Jakarta": 650_000,
    "Bali": 750_000,
    "Bandung": 400_000,
    "Yogyakarta": 380_000,
    "Surabaya": 420_000,
    "Solo": 350_000,
    "Semarang": 360_000,
    "Malang": 340_000,
    "Lombok": 500_000,
}

# Runtime learned averages (updated from search results)
_learned_averages: dict[str, float] = {}


def tag_deals(results: list[dict], travel_type: str) -> list[dict]:
    """
    Analyse results and tag deals with emoji labels.

    Adds field 'deal_tag': '🔥 BEST DEAL' | '✅ GOOD PRICE' | '' to each result.

    Args:
        results: Ranked list of results.
        travel_type: 'train' | 'flight' | 'hotel'.

    Returns:
        Same list with 'deal_tag' added in place.
    """
    if not results:
        return results

    # Learn / update average from current results
    prices = [_get_price(r) for r in results if _get_price(r) > 0]
    if prices:
        avg = sum(prices) / len(prices)
        cache_key = _make_cache_key(results[0], travel_type)
        _learned_averages[cache_key] = avg

    for r in results:
        price = _get_price(r)
        avg = _get_average(r, travel_type, prices)
        r["deal_tag"] = _classify(price, avg)

    deals = [r for r in results if r.get("deal_tag")]
    if deals:
        logger.info(f"[DealDetector] {len(deals)} deal(s) found in {len(results)} results")

    return results


def _classify(price: float, avg: float) -> str:
    if avg <= 0 or price <= 0:
        return ""
    ratio = price / avg
    if ratio < DEAL_THRESHOLD:
        return "🔥 BEST DEAL"
    if ratio < GOOD_THRESHOLD:
        return "✅ GOOD PRICE"
    return ""


def _get_price(r: dict) -> float:
    return float(r.get("price_idr") or r.get("price") or r.get("price_per_night") or 0)


def _make_cache_key(r: dict, travel_type: str) -> str:
    if travel_type == "train":
        return f"train:{r.get('origin','')}:{r.get('destination','')}"
    if travel_type == "flight":
        return f"flight:{r.get('origin','')}:{r.get('destination','')}"
    return f"hotel:{r.get('city','')}"


def _get_average(r: dict, travel_type: str, current_prices: list[float]) -> float:
    """Look up baseline average, fall back to runtime learned, then current median."""
    if travel_type == "train":
        key = (r.get("origin", ""), r.get("destination", ""))
        avg = _TRAIN_AVERAGES.get(key) or _TRAIN_AVERAGES.get((key[1], key[0]))
    elif travel_type == "flight":
        key = (r.get("origin", ""), r.get("destination", ""))
        avg = _FLIGHT_AVERAGES.get(key) or _FLIGHT_AVERAGES.get((key[1], key[0]))
    elif travel_type == "hotel":
        city = r.get("city", "")
        avg = _HOTEL_AVERAGES.get(city)
    else:
        avg = None

    if avg:
        return avg

    # Runtime learned
    cache_key = _make_cache_key(r, travel_type)
    learned = _learned_averages.get(cache_key)
    if learned:
        return learned

    # Fallback: median of current session prices
    if current_prices:
        sorted_p = sorted(current_prices)
        mid = len(sorted_p) // 2
        return sorted_p[mid]

    return 0
