"""
Cheapest Engine – normalises provider results, de-duplicates,
and returns the cheapest N options.

Differences from price_engine.py:
- Accepts raw aggregator output (with _priority field)
- Handles duplicate train/flight offers (same name + departure = dedup)
- Returns richer output including provider priority
- Provides format_price helper

File: services/cheapest_engine.py
"""
from typing import Literal
from utils.logger import logger

TravelType = Literal["train", "flight", "hotel"]

# FX rates to IDR (approximate)
FX_TO_IDR: dict[str, float] = {
    "IDR": 1,
    "USD": 16000,
    "SGD": 11900,
    "MYR": 3400,
    "EUR": 17300,
    "GBP": 20200,
    "JPY": 110,
    "AUD": 10400,
}


def run(
    results: list[dict],
    travel_type: TravelType,
    top_n: int = 5,
) -> list[dict]:
    """
    Process aggregated provider results into clean, ranked cheapest options.

    Steps:
        1. Validate entries (must have positive price).
        2. Normalise prices to IDR.
        3. Remove duplicates (same name + departure time from different providers).
        4. Sort ascending by price; break ties by provider priority.
        5. Attach rank 1..N.

    Args:
        results: Raw output from provider_aggregator (any travel type).
        travel_type: 'train' | 'flight' | 'hotel'.
        top_n: Max results to return.

    Returns:
        Sorted, ranked list of result dicts.
    """
    if not results:
        return []

    # 1. Validate
    valid = [r for r in results if _is_valid(r)]
    if not valid:
        logger.warning(f"[CheapestEngine] No valid results for {travel_type}")
        return []

    # 2. Normalise price → IDR
    for r in valid:
        currency = r.get("currency", "IDR").upper()
        raw_price = r.get("price") or r.get("price_per_night") or 0
        r["price_idr"] = float(raw_price) * FX_TO_IDR.get(currency, 1)
        r["currency"] = "IDR"

    # 3. De-duplicate
    unique = _deduplicate(valid, travel_type)

    # 4. Sort: price_idr ASC, then priority ASC (lower = higher priority)
    sorted_results = sorted(
        unique,
        key=lambda r: (r["price_idr"], r.get("_priority", 99)),
    )

    # 5. Attach rank
    top = sorted_results[:top_n]
    for i, r in enumerate(top, start=1):
        r["rank"] = i
        # Expose normalised price cleanly
        r["price"] = r["price_idr"]

    logger.info(
        f"[CheapestEngine] {travel_type}: {len(valid)} valid → "
        f"{len(unique)} unique → top {len(top)} | "
        f"cheapest Rp {top[0]['price']:,.0f} from {top[0].get('provider','?')}"
        if top else f"[CheapestEngine] {travel_type}: no results after dedup"
    )

    return top


def _is_valid(r: dict) -> bool:
    price = r.get("price") or r.get("price_per_night") or 0
    return isinstance(price, (int, float)) and price > 0


def _deduplicate(results: list[dict], travel_type: str) -> list[dict]:
    """Remove duplicate offers using content-based key per travel type."""
    seen: set[str] = set()
    unique: list[dict] = []

    for r in results:
        key = _dedup_key(r, travel_type)
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique


def _dedup_key(r: dict, travel_type: str) -> str:
    if travel_type == "train":
        name = r.get("train_name") or r.get("name", "")
        return f"{name}|{r.get('departure_time','')}|{r.get('seat_class','')}"
    if travel_type == "flight":
        # Support both normalized (airline+flight_number) and raw (name) formats
        fn = r.get("flight_number") or r.get("name", "")
        return f"{fn}|{r.get('departure_time','')}"
    if travel_type == "hotel":
        name = r.get("hotel_name") or r.get("name", "")
        return f"{name}|{r.get('room_type','')}"
    return str(hash(frozenset(r.items())))


# ─── Formatters ───────────────────────────────────────────────────────────────

def format_price(price: float) -> str:
    """Rp 450.000 style formatting."""
    return f"Rp {price:,.0f}".replace(",", ".")


def format_train_message(results: list[dict]) -> str:
    if not results:
        return "❌ Tidak ditemukan tiket kereta untuk rute tersebut."
    r0 = results[0]
    lines = [
        f"🚂 *Kereta {r0.get('origin','')} → {r0.get('destination','')}*",
        f"📅 {r0.get('date','')}\n",
    ]
    for r in results:
        lines.append(
            f"*{r['rank']}.* {r.get('train_name','?')}\n"
            f"   🕐 {r.get('departure_time','--')} → {r.get('arrival_time','--')}  "
            f"|  🎫 {r.get('seat_class','')}\n"
            f"   💰 *{format_price(r['price'])}*  _(via {r.get('provider','')})_\n"
        )
    lines.append("_Balas nomor untuk pesan tiket. Contoh:_ *1*")
    return "\n".join(lines)


def format_flight_message(results: list[dict]) -> str:
    if not results:
        return "❌ Tidak ditemukan penerbangan untuk rute tersebut."
    r0 = results[0]
    lines = [
        f"✈️ *Penerbangan {r0.get('origin','')} → {r0.get('destination','')}*",
        f"📅 {r0.get('date','')}\n",
    ]
    for r in results:
        dep = (r.get("departure_time") or "")[-5:] or "--:--"
        arr = (r.get("arrival_time") or "")[-5:] or "--:--"
        lines.append(
            f"*{r['rank']}.* {r.get('airline','?')} {r.get('flight_number','')}\n"
            f"   🕐 {dep} → {arr}  |  ⏱ {r.get('duration','')}\n"
            f"   💰 *{format_price(r['price'])}*  _(via {r.get('provider','')})_\n"
        )
    lines.append("_Balas nomor untuk pesan tiket. Contoh:_ *1*")
    return "\n".join(lines)


def format_hotel_message(results: list[dict]) -> str:
    if not results:
        return "\u274c Tidak ditemukan hotel untuk kota tersebut."
    r0 = results[0]
    lines = [
        f"\U0001f3e8 *Hotel di {r0.get('city','')}*",
        f"\U0001f4c5 {r0.get('check_in','')} -> {r0.get('check_out','')}\n",
    ]
    for r in results:
        price = r.get("price_idr") or r.get("price_per_night") or r.get("price") or 0
        stars = "\u2b50" * int(r.get("star_rating") or 0)
        score = r.get("review_score") or 0
        bfast = "\u2705 Sarapan" if r.get("breakfast_included") else "\u274c Tanpa sarapan"
        deal = f"  {r.get('deal_tag','')}" if r.get("deal_tag") else ""
        lines.append(
            f"*{r['rank']}.* {r.get('hotel_name','?')} {stars}{deal}\n"
            f"   \u2b50 {score}/10  |  {bfast}\n"
            f"   \U0001f4b0 *{format_price(price)}/malam*  _(via {r.get('provider','')})_\n"
        )
    lines.append("_Balas nomor untuk pesan. Contoh:_ *1*")
    return "\n".join(lines)


def format_results(travel_type: str, results: list[dict]) -> str:
    if travel_type == "train":
        return format_train_message(results)
    if travel_type == "flight":
        return format_flight_message(results)
    if travel_type == "hotel":
        return format_hotel_message(results)
    return "Tidak ada hasil."
