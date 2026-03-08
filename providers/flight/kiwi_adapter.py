"""
Kiwi (Tequila) API adapter for flight search.

Uses the Kiwi Tequila Flight Search API.
Docs: https://tequila.kiwi.com/portal/docs/tequila_api/search_api
"""
import os
import httpx
from utils.logger import logger
from utils.airport_mapper import city_to_iata

KIWI_API_KEY = os.getenv("KIWI_API_KEY", "")
KIWI_BASE_URL = os.getenv("KIWI_BASE_URL", "https://api.tequila.kiwi.com")
TIMEOUT = 15


async def kiwi_search_flights(
    origin: str,
    destination: str,
    date: str,
    adults: int = 1
) -> list[dict]:
    """Search flights via Kiwi Tequila API."""
    origin_iata = city_to_iata(origin) or origin.upper()
    dest_iata = city_to_iata(destination) or destination.upper()

    logger.info(f"[Kiwi] Searching {origin_iata}→{dest_iata} on {date}")

    if not KIWI_API_KEY:
        logger.warning("[Kiwi] No API key – returning mock data")
        return _mock_kiwi_results(origin_iata, dest_iata, date)

    params = {
        "fly_from": origin_iata,
        "fly_to": dest_iata,
        "date_from": date,
        "date_to": date,
        "adults": adults,
        "currency": "IDR",
        "limit": 10,
        "sort": "price",
        "asc": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{KIWI_BASE_URL}/v2/search",
                params=params,
                headers={"apikey": KIWI_API_KEY},
            )
            resp.raise_for_status()
            data = resp.json()
            raw_results = data.get("data", [])
            results = [_normalise_kiwi(r, origin_iata, dest_iata, date) for r in raw_results]
            logger.info(f"[Kiwi] Got {len(results)} results")
            return results
    except Exception as e:
        logger.error(f"[Kiwi] Error: {e}")

    return _mock_kiwi_results(origin_iata, dest_iata, date)


def _normalise_kiwi(raw: dict, origin: str, dest: str, date: str) -> dict:
    from datetime import datetime
    dep_ts = raw.get("dTime", 0)
    arr_ts = raw.get("aTime", 0)
    dep_str = datetime.fromtimestamp(dep_ts).strftime("%Y-%m-%dT%H:%M") if dep_ts else ""
    arr_str = datetime.fromtimestamp(arr_ts).strftime("%Y-%m-%dT%H:%M") if arr_ts else ""

    routes = raw.get("route", [{}])
    airline = routes[0].get("airline", "Unknown") if routes else "Unknown"
    flight_no = f"{routes[0].get('airline','')}{routes[0].get('flight_no','')}" if routes else ""

    return {
        "provider": "Kiwi",
        "flight_number": flight_no,
        "airline": airline,
        "origin": origin,
        "destination": dest,
        "date": date,
        "departure_time": dep_str,
        "arrival_time": arr_str,
        "duration": f"{raw.get('fly_duration', '')}",
        "cabin_class": "Ekonomi",
        "price": float(raw.get("price", 0)),
        "currency": raw.get("currency", "IDR"),
        "seats_available": raw.get("availability", {}).get("seats"),
        "source": "kiwi_api",
    }


def _mock_kiwi_results(origin: str, dest: str, date: str) -> list[dict]:
    return [
        {
            "provider": "Kiwi",
            "flight_number": "QZ8074",
            "airline": "AirAsia",
            "origin": origin,
            "destination": dest,
            "date": date,
            "departure_time": f"{date}T06:00",
            "arrival_time": f"{date}T07:30",
            "duration": "1j 30m",
            "cabin_class": "Ekonomi",
            "price": 580000,
            "currency": "IDR",
            "seats_available": 18,
            "source": "kiwi_mock",
        },
        {
            "provider": "Kiwi",
            "flight_number": "IW1234",
            "airline": "Wings Air",
            "origin": origin,
            "destination": dest,
            "date": date,
            "departure_time": f"{date}T14:00",
            "arrival_time": f"{date}T15:30",
            "duration": "1j 30m",
            "cabin_class": "Ekonomi",
            "price": 540000,
            "currency": "IDR",
            "seats_available": 22,
            "source": "kiwi_mock",
        },
    ]
