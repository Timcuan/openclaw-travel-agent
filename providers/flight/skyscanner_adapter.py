"""
Skyscanner API adapter for flight search.

Uses Skyscanner Partners API.
Docs: https://developers.skyscanner.net
"""
import os
import httpx
from utils.logger import logger
from utils.airport_mapper import city_to_iata

SKYSCANNER_API_KEY = os.getenv("SKYSCANNER_API_KEY", "")
SKYSCANNER_BASE_URL = os.getenv("SKYSCANNER_BASE_URL", "https://partners.api.skyscanner.net")
TIMEOUT = 15


async def skyscanner_search_flights(
    origin: str,
    destination: str,
    date: str,
    adults: int = 1
) -> list[dict]:
    """Search flights via Skyscanner Live Prices."""
    origin_iata = city_to_iata(origin) or origin.upper()
    dest_iata = city_to_iata(destination) or destination.upper()

    logger.info(f"[Skyscanner] Searching {origin_iata}→{dest_iata} on {date}")

    if not SKYSCANNER_API_KEY:
        logger.warning("[Skyscanner] No API key – returning mock data")
        return _mock_skyscanner_results(origin_iata, dest_iata, date)

    # Skyscanner uses YYYY-MM format for month-based queries
    date_parts = date.split("-")
    outbound_date = f"{date_parts[0]}-{date_parts[1]}" if len(date_parts) >= 2 else date

    headers = {
        "x-api-key": SKYSCANNER_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "query": {
            "market": "ID",
            "locale": "id-ID",
            "currency": "IDR",
            "queryLegs": [
                {
                    "originPlaceId": {"iata": origin_iata},
                    "destinationPlaceId": {"iata": dest_iata},
                    "date": {
                        "year": int(date_parts[0]),
                        "month": int(date_parts[1]),
                        "day": int(date_parts[2]) if len(date_parts) > 2 else 1,
                    },
                }
            ],
            "adults": adults,
            "cabinClass": "CABIN_CLASS_ECONOMY",
        }
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{SKYSCANNER_BASE_URL}/apiservices/v3/flights/live/search/create",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            raw_itineraries = (
                data.get("content", {})
                .get("results", {})
                .get("itineraries", {})
            )
            results = []
            for itin_id, itin in list(raw_itineraries.items())[:10]:
                r = _normalise_skyscanner(itin, origin_iata, dest_iata, date)
                if r:
                    results.append(r)
            logger.info(f"[Skyscanner] Got {len(results)} results")
            return results
    except Exception as e:
        logger.error(f"[Skyscanner] Error: {e}")

    return _mock_skyscanner_results(origin_iata, dest_iata, date)


def _normalise_skyscanner(raw: dict, origin: str, dest: str, date: str) -> dict:
    try:
        price_info = raw.get("pricingOptions", [{}])[0]
        price = float(price_info.get("price", {}).get("amount", 0))
        agent = price_info.get("agentIds", ["Unknown"])[0]
    except (IndexError, ValueError, KeyError):
        price, agent = 0, "Unknown"

    leg = raw.get("legIds", [""])[0]

    return {
        "provider": "Skyscanner",
        "flight_number": leg[:10] if leg else "Unknown",
        "airline": agent,
        "origin": origin,
        "destination": dest,
        "date": date,
        "departure_time": "",
        "arrival_time": "",
        "duration": "",
        "cabin_class": "Ekonomi",
        "price": price,
        "currency": "IDR",
        "seats_available": None,
        "source": "skyscanner_api",
    }


def _mock_skyscanner_results(origin: str, dest: str, date: str) -> list[dict]:
    return [
        {
            "provider": "Skyscanner",
            "flight_number": "SJ072",
            "airline": "Sriwijaya Air",
            "origin": origin,
            "destination": dest,
            "date": date,
            "departure_time": f"{date}T09:00",
            "arrival_time": f"{date}T10:35",
            "duration": "1j 35m",
            "cabin_class": "Ekonomi",
            "price": 595000,
            "currency": "IDR",
            "seats_available": 14,
            "source": "skyscanner_mock",
        },
        {
            "provider": "Skyscanner",
            "flight_number": "IN303",
            "airline": "Citilink",
            "origin": origin,
            "destination": dest,
            "date": date,
            "departure_time": f"{date}T16:00",
            "arrival_time": f"{date}T17:30",
            "duration": "1j 30m",
            "cabin_class": "Ekonomi",
            "price": 560000,
            "currency": "IDR",
            "seats_available": 28,
            "source": "skyscanner_mock",
        },
    ]
