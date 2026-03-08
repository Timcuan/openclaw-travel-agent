"""
Result Normalizer – converts raw provider dicts to NormalizedResult objects
and ensures a consistent schema across all providers.

File: services/result_normalizer.py
"""
from providers.base_provider import NormalizedResult
from utils.logger import logger

# FX to IDR
FX: dict[str, float] = {
    "IDR": 1, "USD": 16000, "SGD": 11900,
    "MYR": 3400, "EUR": 17300, "GBP": 20200,
}


def normalize_train(raw: dict, provider_name: str = "") -> NormalizedResult:
    price = _to_idr(raw.get("price", 0), raw.get("currency", "IDR"))
    return NormalizedResult(
        travel_type="train",
        provider=provider_name or raw.get("provider", ""),
        name=raw.get("train_name", "Unknown"),
        origin=raw.get("origin", ""),
        destination=raw.get("destination", ""),
        date=raw.get("date", ""),
        departure=raw.get("departure_time", ""),
        arrival=raw.get("arrival_time", ""),
        duration=raw.get("duration", ""),
        price=price,
        seat_class=raw.get("seat_class", "ekonomi"),
        available_seats=raw.get("available_seats"),
        provider_ref=raw.get("provider_ref", ""),
        raw=raw,
    )


def normalize_flight(raw: dict, provider_name: str = "") -> NormalizedResult:
    price = _to_idr(raw.get("price", 0), raw.get("currency", "IDR"))
    dep = raw.get("departure_time", "")
    arr = raw.get("arrival_time", "")
    return NormalizedResult(
        travel_type="flight",
        provider=provider_name or raw.get("provider", ""),
        name=f"{raw.get('airline','')} {raw.get('flight_number','')}".strip(),
        origin=raw.get("origin", ""),
        destination=raw.get("destination", ""),
        date=raw.get("date", ""),
        departure=dep[-5:] if dep else "",
        arrival=arr[-5:] if arr else "",
        duration=raw.get("duration", ""),
        price=price,
        seat_class=raw.get("cabin_class", "ekonomi"),
        available_seats=raw.get("seats_available"),
        provider_ref=raw.get("provider_ref", ""),
        raw=raw,
    )


def normalize_hotel(raw: dict, provider_name: str = "") -> NormalizedResult:
    price = _to_idr(
        raw.get("price_per_night") or raw.get("price", 0),
        raw.get("currency", "IDR"),
    )
    return NormalizedResult(
        travel_type="hotel",
        provider=provider_name or raw.get("provider", ""),
        name=raw.get("hotel_name", "Unknown Hotel"),
        city=raw.get("city", ""),
        check_in=raw.get("check_in", ""),
        check_out=raw.get("check_out", ""),
        price=price,
        star_rating=int(raw.get("star_rating", 0)),
        review_score=float(raw.get("review_score", 0)),
        breakfast_included=bool(raw.get("breakfast_included", False)),
        cancellation_policy=raw.get("cancellation_policy", ""),
        image_url=raw.get("image_url", ""),
        provider_ref=raw.get("provider_ref", ""),
        raw=raw,
    )


def normalize_many(
    raws: list[dict],
    travel_type: str,
    provider_name: str = "",
) -> list[NormalizedResult]:
    """Normalize a list of raw dicts. Skips entries that throw."""
    results = []
    fn = {"train": normalize_train, "flight": normalize_flight, "hotel": normalize_hotel}.get(travel_type)
    if fn is None:
        logger.warning(f"[Normalizer] Unknown travel_type: {travel_type}")
        return results
    for raw in raws:
        try:
            results.append(fn(raw, provider_name))
        except Exception as e:
            logger.debug(f"[Normalizer] Skipped result: {e}")
    return results


def _to_idr(amount, currency: str) -> float:
    rate = FX.get(str(currency).upper(), 1)
    try:
        return float(amount) * rate
    except (TypeError, ValueError):
        return 0.0
