"""
Traveloka adapter for train search.

Uses Traveloka's API (unofficial / reverse-engineered).
Falls back to mock data if API key is not configured.
"""
import os
import httpx
from utils.logger import logger
from utils.city_mapper import city_to_station

TRAVELOKA_API_KEY = os.getenv("TRAVELOKA_API_KEY", "")
TRAVELOKA_BASE_URL = os.getenv("TRAVELOKA_BASE_URL", "https://api.traveloka.com")
TIMEOUT = 15


async def traveloka_search_trains(
    origin: str,
    destination: str,
    date: str,
    adult: int = 1
) -> list[dict]:
    """Search trains via Traveloka."""
    origin_code = city_to_station(origin) or origin.upper()
    dest_code = city_to_station(destination) or destination.upper()

    logger.info(f"[Traveloka] Searching train {origin_code}→{dest_code} on {date}")

    if not TRAVELOKA_API_KEY:
        logger.warning("[Traveloka] No API key – returning mock data")
        return _mock_traveloka_results(origin_code, dest_code, date)

    payload = {
        "origin": origin_code,
        "destination": dest_code,
        "departDate": date,
        "numOfAdult": adult,
        "currency": "IDR",
    }
    headers = {
        "X-API-Key": TRAVELOKA_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{TRAVELOKA_BASE_URL}/train/search",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            raw_results = data.get("data", {}).get("results", [])
            results = [_normalise_traveloka(r, origin_code, dest_code, date) for r in raw_results]
            logger.info(f"[Traveloka] Got {len(results)} results")
            return results
    except Exception as e:
        logger.error(f"[Traveloka] Error: {e}")

    return _mock_traveloka_results(origin_code, dest_code, date)


def _normalise_traveloka(raw: dict, origin: str, dest: str, date: str) -> dict:
    return {
        "provider": "Traveloka",
        "train_name": raw.get("name", "Unknown"),
        "origin": origin,
        "destination": dest,
        "date": date,
        "departure_time": raw.get("departureTime", "--:--"),
        "arrival_time": raw.get("arrivalTime", "--:--"),
        "duration": raw.get("journeyDuration"),
        "seat_class": raw.get("seatClass", "Ekonomi"),
        "price": float(raw.get("lowestPrice", {}).get("amount", 0)),
        "currency": "IDR",
        "available_seats": raw.get("seatAvailability"),
        "source": "traveloka_api",
    }


def _mock_traveloka_results(origin: str, dest: str, date: str) -> list[dict]:
    return [
        {
            "provider": "Traveloka",
            "train_name": "Argo Lawu",
            "origin": origin,
            "destination": dest,
            "date": date,
            "departure_time": "08:05",
            "arrival_time": "16:40",
            "duration": "8j 35m",
            "seat_class": "Eksekutif",
            "price": 455000,
            "currency": "IDR",
            "available_seats": 25,
            "source": "traveloka_mock",
        },
        {
            "provider": "Traveloka",
            "train_name": "Kertajaya",
            "origin": origin,
            "destination": dest,
            "date": date,
            "departure_time": "22:00",
            "arrival_time": "06:30+1",
            "duration": "8j 30m",
            "seat_class": "Ekonomi",
            "price": 275000,
            "currency": "IDR",
            "available_seats": 40,
            "source": "traveloka_mock",
        },
    ]
