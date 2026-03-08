"""
Amadeus API adapter for flight search (Indonesia domestic).

Uses the Amadeus REST API v2 (test & production).
Docs: https://developers.amadeus.com
"""
import os
import httpx
from utils.logger import logger
from utils.airport_mapper import city_to_iata

AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID", "")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET", "")
AMADEUS_BASE_URL = os.getenv("AMADEUS_BASE_URL", "https://test.api.amadeus.com")
TIMEOUT = 20

_access_token: str = ""
_token_expiry: float = 0.0


async def _get_access_token() -> str:
    """Fetch or reuse Amadeus OAuth2 token."""
    import time
    global _access_token, _token_expiry

    if _access_token and time.time() < _token_expiry - 60:
        return _access_token

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{AMADEUS_BASE_URL}/v1/security/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": AMADEUS_CLIENT_ID,
                    "client_secret": AMADEUS_CLIENT_SECRET,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            _access_token = data["access_token"]
            _token_expiry = time.time() + data.get("expires_in", 1799)
            return _access_token
    except Exception as e:
        logger.error(f"[Amadeus] Token error: {e}")
        return ""


async def amadeus_search_flights(
    origin: str,
    destination: str,
    date: str,
    adults: int = 1
) -> list[dict]:
    """Search flights via Amadeus Flight Offers Search v2."""
    origin_iata = city_to_iata(origin) or origin.upper()
    dest_iata = city_to_iata(destination) or destination.upper()

    logger.info(f"[Amadeus] Searching {origin_iata}→{dest_iata} on {date}")

    if not AMADEUS_CLIENT_ID:
        logger.warning("[Amadeus] No credentials – returning mock data")
        return _mock_amadeus_results(origin_iata, dest_iata, date)

    token = await _get_access_token()
    if not token:
        return _mock_amadeus_results(origin_iata, dest_iata, date)

    params = {
        "originLocationCode": origin_iata,
        "destinationLocationCode": dest_iata,
        "departureDate": date,
        "adults": adults,
        "currencyCode": "IDR",
        "max": 10,
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{AMADEUS_BASE_URL}/v2/shopping/flight-offers",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            data = resp.json()
            raw_offers = data.get("data", [])
            results = [_normalise_amadeus(o, origin_iata, dest_iata, date) for o in raw_offers]
            logger.info(f"[Amadeus] Got {len(results)} offers")
            return results
    except Exception as e:
        logger.error(f"[Amadeus] Error: {e}")

    return _mock_amadeus_results(origin_iata, dest_iata, date)


def _normalise_amadeus(raw: dict, origin: str, dest: str, date: str) -> dict:
    try:
        seg = raw["itineraries"][0]["segments"][0]
        price = float(raw["price"]["grandTotal"])
        currency = raw["price"]["currency"]
        dep = seg.get("departure", {})
        arr = seg.get("arrival", {})
        duration = raw["itineraries"][0].get("duration", "")
    except (KeyError, IndexError, ValueError):
        price, currency, dep, arr, duration = 0, "IDR", {}, {}, ""

    return {
        "provider": "Amadeus",
        "flight_number": f"{seg.get('carrierCode','')}{seg.get('number','')}",
        "airline": seg.get("carrierCode", "Unknown"),
        "origin": origin,
        "destination": dest,
        "date": date,
        "departure_time": dep.get("at", "")[:16],
        "arrival_time": arr.get("at", "")[:16],
        "duration": duration,
        "cabin_class": "Ekonomi",
        "price": price,
        "currency": currency,
        "seats_available": raw.get("numberOfBookableSeats"),
        "source": "amadeus_api",
    }


def _mock_amadeus_results(origin: str, dest: str, date: str) -> list[dict]:
    return [
        {
            "provider": "Amadeus",
            "flight_number": "GA102",
            "airline": "Garuda Indonesia",
            "origin": origin,
            "destination": dest,
            "date": date,
            "departure_time": f"{date}T07:00",
            "arrival_time": f"{date}T08:30",
            "duration": "1j 30m",
            "cabin_class": "Ekonomi",
            "price": 850000,
            "currency": "IDR",
            "seats_available": 20,
            "source": "amadeus_mock",
        },
        {
            "provider": "Amadeus",
            "flight_number": "JT204",
            "airline": "Lion Air",
            "origin": origin,
            "destination": dest,
            "date": date,
            "departure_time": f"{date}T10:00",
            "arrival_time": f"{date}T11:35",
            "duration": "1j 35m",
            "cabin_class": "Ekonomi",
            "price": 620000,
            "currency": "IDR",
            "seats_available": 35,
            "source": "amadeus_mock",
        },
    ]
