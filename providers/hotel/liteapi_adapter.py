"""
LiteAPI hotel search adapter.

LiteAPI is a hotel booking API for Southeast Asia.
Docs: https://docs.liteapi.travel
"""
import os
import httpx
from utils.logger import logger

LITEAPI_KEY = os.getenv("LITEAPI_KEY", "")
LITEAPI_BASE_URL = os.getenv("LITEAPI_BASE_URL", "https://api.liteapi.travel/v3.0")
TIMEOUT = 15


async def liteapi_search_hotels(
    city: str,
    check_in: str,
    check_out: str,
    adults: int = 2,
    rooms: int = 1
) -> list[dict]:
    """Search hotels via LiteAPI."""
    logger.info(f"[LiteAPI] Searching hotels in {city} {check_in}→{check_out}")

    if not LITEAPI_KEY:
        logger.warning("[LiteAPI] No API key – returning mock data")
        return _mock_liteapi_results(city, check_in, check_out)

    headers = {
        "X-API-Key": LITEAPI_KEY,
        "Content-Type": "application/json",
    }
    params = {
        "cityName": city,
        "checkIn": check_in,
        "checkOut": check_out,
        "adults": adults,
        "rooms": rooms,
        "currency": "IDR",
        "country": "ID",
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{LITEAPI_BASE_URL}/hotels",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            raw_hotels = data.get("data", [])
            results = [_normalise_liteapi(h, city, check_in, check_out) for h in raw_hotels]
            logger.info(f"[LiteAPI] Got {len(results)} results")
            return results
    except Exception as e:
        logger.error(f"[LiteAPI] Error: {e}")

    return _mock_liteapi_results(city, check_in, check_out)


def _normalise_liteapi(raw: dict, city: str, check_in: str, check_out: str) -> dict:
    rates = raw.get("minRate", {})
    return {
        "provider": "LiteAPI",
        "hotel_name": raw.get("name", "Unknown Hotel"),
        "city": city,
        "address": raw.get("address", ""),
        "check_in": check_in,
        "check_out": check_out,
        "star_rating": raw.get("stars", 0),
        "review_score": raw.get("rating", 0),
        "price_per_night": float(rates.get("amount", 0)),
        "total_price": float(rates.get("totalAmount", 0)),
        "currency": rates.get("currency", "IDR"),
        "room_type": raw.get("roomType", "Standard"),
        "breakfast_included": raw.get("boardType", "").lower() in ("bb", "hb", "fb", "ai"),
        "cancellation_policy": raw.get("cancellationPolicy", "Non-refundable"),
        "image_url": raw.get("thumbnail", ""),
        "source": "liteapi_api",
    }


def _mock_liteapi_results(city: str, check_in: str, check_out: str) -> list[dict]:
    return [
        {
            "provider": "LiteAPI",
            "hotel_name": f"Aston {city} Hotel",
            "city": city,
            "address": f"Jl. Pemuda No.1, {city}",
            "check_in": check_in,
            "check_out": check_out,
            "star_rating": 4,
            "review_score": 8.2,
            "price_per_night": 480000,
            "total_price": 480000,
            "currency": "IDR",
            "room_type": "Deluxe Room",
            "breakfast_included": True,
            "cancellation_policy": "Free cancellation until 24h before",
            "image_url": "",
            "source": "liteapi_mock",
        },
        {
            "provider": "LiteAPI",
            "hotel_name": f"Ibis Budget {city}",
            "city": city,
            "address": f"Jl. Raya No.20, {city}",
            "check_in": check_in,
            "check_out": check_out,
            "star_rating": 2,
            "review_score": 7.5,
            "price_per_night": 280000,
            "total_price": 280000,
            "currency": "IDR",
            "room_type": "Standard Room",
            "breakfast_included": False,
            "cancellation_policy": "Non-refundable",
            "image_url": "",
            "source": "liteapi_mock",
        },
    ]
