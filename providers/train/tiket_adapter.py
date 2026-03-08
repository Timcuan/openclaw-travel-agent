"""
Tiket.com API adapter for train search.

Uses Tiket.com's API (unofficial/reverse-engineered).
Falls back to mock data if API key is not configured.
"""
import os
from typing import Optional
import httpx
from utils.logger import logger
from utils.city_mapper import city_to_station

TIKET_API_KEY = os.getenv("TIKET_API_KEY", "")
TIKET_BASE_URL = os.getenv("TIKET_BASE_URL", "https://api.tiket.com")
TIMEOUT = 15


async def tiket_search_trains(
    origin: str,
    destination: str,
    date: str,
    adult: int = 1
) -> list[dict]:
    """
    Search train tickets via Tiket.com.

    Args:
        origin: City name or station code
        destination: City name or station code
        date: YYYY-MM-DD
        adult: Passenger count

    Returns:
        Normalised list of train results.
    """
    origin_code = city_to_station(origin) or origin.upper()
    dest_code = city_to_station(destination) or destination.upper()

    logger.info(f"[Tiket] Searching train {origin_code}→{dest_code} on {date}")

    if not TIKET_API_KEY:
        logger.warning("[Tiket] No API key configured – returning mock data")
        return _mock_tiket_results(origin_code, dest_code, date)

    params = {
        "from": origin_code,
        "to": dest_code,
        "departureDate": date,
        "pax": adult,
    }
    headers = {
        "Authorization": f"Bearer {TIKET_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{TIKET_BASE_URL}/v2/train/search",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            raw_results = data.get("data", {}).get("trains", [])
            results = [_normalise_tiket(r, origin_code, dest_code, date) for r in raw_results]
            logger.info(f"[Tiket] Got {len(results)} results")
            return results
    except httpx.HTTPStatusError as e:
        logger.error(f"[Tiket] HTTP error {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        logger.error(f"[Tiket] Error: {e}")

    return _mock_tiket_results(origin_code, dest_code, date)


def _normalise_tiket(raw: dict, origin: str, dest: str, date: str) -> dict:
    return {
        "provider": "Tiket",
        "train_name": raw.get("trainName", "Unknown"),
        "origin": origin,
        "destination": dest,
        "date": date,
        "departure_time": raw.get("departureTime", "--:--"),
        "arrival_time": raw.get("arrivalTime", "--:--"),
        "duration": raw.get("duration"),
        "seat_class": raw.get("seatClass", "Ekonomi"),
        "price": float(raw.get("price", {}).get("amount", 0)),
        "currency": raw.get("price", {}).get("currency", "IDR"),
        "available_seats": raw.get("availableSeats"),
        "source": "tiket_api",
    }


def _mock_tiket_results(origin: str, dest: str, date: str) -> list[dict]:
    return [
        {
            "provider": "Tiket",
            "train_name": "Argo Wilis",
            "origin": origin,
            "destination": dest,
            "date": date,
            "departure_time": "07:00",
            "arrival_time": "15:30",
            "duration": "8j 30m",
            "seat_class": "Eksekutif",
            "price": 460000,
            "currency": "IDR",
            "available_seats": 12,
            "source": "tiket_mock",
        },
        {
            "provider": "Tiket",
            "train_name": "Bima",
            "origin": origin,
            "destination": dest,
            "date": date,
            "departure_time": "17:00",
            "arrival_time": "04:20+1",
            "duration": "11j 20m",
            "seat_class": "Eksekutif",
            "price": 520000,
            "currency": "IDR",
            "available_seats": 8,
            "source": "tiket_mock",
        },
    ]
