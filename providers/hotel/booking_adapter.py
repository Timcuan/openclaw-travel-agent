"""
Booking.com Demand API adapter for hotel search.

Uses Booking.com's Affiliate Partner API.
Docs: https://developers.booking.com
"""
import os
import httpx
from utils.logger import logger

BOOKING_CLIENT_ID = os.getenv("BOOKING_CLIENT_ID", "")
BOOKING_CLIENT_SECRET = os.getenv("BOOKING_CLIENT_SECRET", "")
BOOKING_BASE_URL = "https://demandapi.booking.com/3.1"
TIMEOUT = 15


async def booking_search_hotels(
    city: str,
    check_in: str,
    check_out: str,
    adults: int = 2,
    rooms: int = 1
) -> list[dict]:
    """Search hotels via Booking.com Partner API."""
    logger.info(f"[Booking] Searching hotels in {city} {check_in}→{check_out}")

    if not BOOKING_CLIENT_ID:
        logger.warning("[Booking] No credentials – returning mock data")
        return _mock_booking_results(city, check_in, check_out)

    # Booking.com uses Basic Auth
    import base64
    credentials = base64.b64encode(
        f"{BOOKING_CLIENT_ID}:{BOOKING_CLIENT_SECRET}".encode()
    ).decode()

    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    params = {
        "city": city,
        "checkin": check_in,
        "checkout": check_out,
        "adults_count": adults,
        "room_count": rooms,
        "currency": "IDR",
        "country_of_origin": "ID",
        "rows": 10,
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{BOOKING_BASE_URL}/accommodations/search",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            raw_hotels = data.get("data", [])
            results = [_normalise_booking(h, city, check_in, check_out) for h in raw_hotels]
            logger.info(f"[Booking] Got {len(results)} results")
            return results
    except Exception as e:
        logger.error(f"[Booking] Error: {e}")

    return _mock_booking_results(city, check_in, check_out)


def _normalise_booking(raw: dict, city: str, check_in: str, check_out: str) -> dict:
    price_info = raw.get("composite_price_breakdown", {})
    price = price_info.get("gross_amount_per_night", {}).get("value", 0)
    return {
        "provider": "Booking.com",
        "hotel_name": raw.get("name", "Unknown Hotel"),
        "city": city,
        "address": raw.get("address", {}).get("street", ""),
        "check_in": check_in,
        "check_out": check_out,
        "star_rating": raw.get("class", 0),
        "review_score": raw.get("review_score", 0),
        "price_per_night": float(price),
        "total_price": float(price),
        "currency": "IDR",
        "room_type": raw.get("room_name", "Standard"),
        "breakfast_included": raw.get("breakfast_included", False),
        "cancellation_policy": "See details",
        "image_url": raw.get("main_photo_url", ""),
        "source": "booking_api",
    }


def _mock_booking_results(city: str, check_in: str, check_out: str) -> list[dict]:
    return [
        {
            "provider": "Booking.com",
            "hotel_name": f"Grand Mercure {city}",
            "city": city,
            "address": f"Jl. Sudirman No.55, {city}",
            "check_in": check_in,
            "check_out": check_out,
            "star_rating": 5,
            "review_score": 8.8,
            "price_per_night": 750000,
            "total_price": 750000,
            "currency": "IDR",
            "room_type": "Superior Room",
            "breakfast_included": True,
            "cancellation_policy": "Free cancellation",
            "image_url": "",
            "source": "booking_mock",
        },
        {
            "provider": "Booking.com",
            "hotel_name": f"Pop! Hotel {city}",
            "city": city,
            "address": f"Jl. Diponegoro No.12, {city}",
            "check_in": check_in,
            "check_out": check_out,
            "star_rating": 2,
            "review_score": 7.8,
            "price_per_night": 250000,
            "total_price": 250000,
            "currency": "IDR",
            "room_type": "Pop Room",
            "breakfast_included": False,
            "cancellation_policy": "Non-refundable",
            "image_url": "",
            "source": "booking_mock",
        },
    ]
