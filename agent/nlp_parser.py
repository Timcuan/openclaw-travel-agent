"""
Smart NLP Parser – enhanced intent detection for Indonesian travel queries.

Improvements over intent_parser.py:
- Richer date parsing (malam ini, besok pagi, akhir pekan, etc.)
- Passenger count detection (2 orang, 3 penumpang)
- Seat class detection (bisnis, eksekutif, ekonomi)
- Better city extraction with fuzz matching
- Structured ParsedIntent dataclass

File: agent/nlp_parser.py
"""
import os
import re
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional
import httpx

from utils.location_resolver import (
    resolve_train_station,
    resolve_airport,
    resolve_hotel_city,
    INDONESIAN_CITIES,
)
from utils.date_parser import parse_date as _parse_date_module
from utils.logger import logger

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = "https://api.openai.com/v1"

# ─── Data class ───────────────────────────────────────────────────────────────

@dataclass
class ParsedIntent:
    intent: str                         # search_train | search_flight | search_hotel | booking | unknown
    origin: Optional[str] = None        # city name or code
    destination: Optional[str] = None
    city: Optional[str] = None          # for hotels
    date: Optional[str] = None          # YYYY-MM-DD
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    passengers: int = 1
    rooms: int = 1
    seat_class: Optional[str] = None    # ekonomi | bisnis | eksekutif
    option_number: Optional[int] = None # for booking selection
    raw_query: str = ""
    message: Optional[str] = None      # for unknown intent

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


# ─── GPT system prompt ────────────────────────────────────────────────────────

GPT_SYSTEM = """You are a travel intent parser for Indonesian domestic travel.
Parse the user's text and return ONLY a valid JSON object.

Today's date: {today}

JSON fields (use null for missing):
- intent: "search_train" | "search_flight" | "search_hotel" | "booking" | "unknown"
- origin: city name (for train/flight)
- destination: city name (for train/flight)
- city: hotel city name
- date: YYYY-MM-DD (for train/flight)
- check_in: YYYY-MM-DD (for hotel)
- check_out: YYYY-MM-DD (for hotel, default check_in + 1 day)
- passengers: integer (default 1 for train/flight, 2 for hotel)
- rooms: integer (default 1)
- seat_class: "ekonomi" | "bisnis" | "eksekutif" | null
- option_number: integer (when user picks option 1, 2, 3...)
- message: error message if unknown

Date keywords:
- "besok" = tomorrow
- "besok pagi" = tomorrow
- "besok malam" = tomorrow
- "lusa" = day after tomorrow
- "malam ini" = today
- "akhir pekan" / "sabtu" = coming Saturday
- "minggu depan" = next Monday
- "minggu ini" = this Sunday

Passenger keywords:
- "2 orang", "dua orang", "berdua" → 2
- "3 orang", "tiga orang", "bertiga" → 3
- "4 orang" → 4

Seat class keywords:
- "bisnis" → bisnis
- "eksekutif" → eksekutif
- "ekonomi" / default → ekonomi
"""


# ─── Main parser ──────────────────────────────────────────────────────────────

async def parse_intent(text: str) -> ParsedIntent:
    """
    Parse natural language Indonesian travel query.
    Uses GPT if available, falls back to rule-based parser.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    raw = text.strip()

    if OPENAI_API_KEY:
        result = await _gpt_parse(raw, today)
        if result:
            result.raw_query = raw
            return result

    result = _rule_parse(raw, today)
    result.raw_query = raw
    return result


# ─── GPT parser ───────────────────────────────────────────────────────────────

async def _gpt_parse(text: str, today: str) -> Optional[ParsedIntent]:
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": GPT_SYSTEM.format(today=today)},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
    }
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.post(f"{OPENAI_BASE_URL}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            raw_dict = json.loads(content)
            return _dict_to_intent(raw_dict)
    except Exception as e:
        logger.warning(f"[NLPParser] GPT failed: {e}")
        return None


def _dict_to_intent(d: dict) -> ParsedIntent:
    return ParsedIntent(
        intent=d.get("intent", "unknown"),
        origin=d.get("origin"),
        destination=d.get("destination"),
        city=d.get("city"),
        date=d.get("date"),
        check_in=d.get("check_in"),
        check_out=d.get("check_out"),
        passengers=int(d.get("passengers") or 1),
        rooms=int(d.get("rooms") or 1),
        seat_class=d.get("seat_class"),
        option_number=d.get("option_number"),
        message=d.get("message"),
    )


# ─── Rule-based fallback parser ───────────────────────────────────────────────

TRAIN_KW  = ["kereta", "krl", " ka ", "train", "kereta api", "tiket kereta"]
FLIGHT_KW = ["pesawat", "terbang", "flight", "penerbangan", "tiket pesawat", "pesan tiket pesawat"]
HOTEL_KW  = ["hotel", "penginapan", "menginap", "kamar hotel", "villa", "cari hotel", "booking hotel"]


def _rule_parse(text: str, today: str) -> ParsedIntent:
    low = text.lower()
    today_dt = datetime.strptime(today, "%Y-%m-%d")
    # Use the superior date_parser module for date resolution
    date_str = _parse_date_module(low, reference=today_dt)
    passengers = _parse_passengers(low)
    seat_class = _parse_seat_class(low)

    # ── booking selection ────────────────────────────────────────
    if re.match(r"^\s*\d+\s*$", low) or low in ("pilih 1", "pilih 2", "pilih 3"):
        num = int(re.search(r"\d+", low).group())
        return ParsedIntent(intent="booking", option_number=num)

    # ── train ────────────────────────────────────────────────────
    if any(k in low for k in TRAIN_KW):
        cities = _extract_cities(low)
        return ParsedIntent(
            intent="search_train",
            origin=cities[0] if len(cities) > 0 else None,
            destination=cities[1] if len(cities) > 1 else None,
            date=date_str,
            passengers=passengers,
            seat_class=seat_class or "ekonomi",
        )

    # ── flight ───────────────────────────────────────────────────
    if any(k in low for k in FLIGHT_KW):
        cities = _extract_cities(low)
        return ParsedIntent(
            intent="search_flight",
            origin=cities[0] if len(cities) > 0 else None,
            destination=cities[1] if len(cities) > 1 else None,
            date=date_str,
            passengers=passengers,
            seat_class=seat_class or "ekonomi",
        )

    # ── hotel ────────────────────────────────────────────────────
    if any(k in low for k in HOTEL_KW):
        cities = _extract_cities(low)
        city = cities[0] if cities else None
        nights = _parse_nights(low)
        check_in_dt = datetime.strptime(date_str, "%Y-%m-%d")
        check_out_dt = check_in_dt + timedelta(days=nights)
        return ParsedIntent(
            intent="search_hotel",
            city=city,
            check_in=date_str,
            check_out=check_out_dt.strftime("%Y-%m-%d"),
            passengers=passengers,
            rooms=1,
        )

    return ParsedIntent(
        intent="unknown",
        message=(
            "Maaf, saya tidak mengerti. Coba:\n"
            "• `kereta surabaya jakarta besok`\n"
            "• `pesawat bali jakarta besok`\n"
            "• `hotel bandung 2 malam`"
        ),
    )


# ─── Helper: date parsing ─────────────────────────────────────────────────────

    # Note: date parsing is now handled by _parse_date_module above
    return (today + timedelta(days=1)).strftime("%Y-%m-%d")


def _parse_passengers(low: str) -> int:
    WORD_NUMS = {"dua": 2, "tiga": 3, "empat": 4, "lima": 5}
    for word, n in WORD_NUMS.items():
        if word in low:
            return n
    if "berdua" in low:
        return 2
    if "bertiga" in low:
        return 3
    m = re.search(r"(\d+)\s*(orang|penumpang|pax|tiket)", low)
    if m:
        return max(1, min(9, int(m.group(1))))
    return 1


def _parse_seat_class(low: str) -> Optional[str]:
    if "eksekutif" in low or "executive" in low or "first" in low:
        return "eksekutif"
    if "bisnis" in low or "business" in low:
        return "bisnis"
    if "ekonomi" in low or "economy" in low:
        return "ekonomi"
    return None


def _parse_nights(low: str) -> int:
    m = re.search(r"(\d+)\s*(malam|hari|night)", low)
    if m:
        return max(1, int(m.group(1)))
    return 1


def _extract_cities(low: str) -> list[str]:
    """Find city names in order of appearance."""
    found_positions = []
    for city in INDONESIAN_CITIES:
        idx = low.find(city.lower())
        if idx != -1:
            found_positions.append((idx, city.capitalize()))
    found_positions.sort(key=lambda x: x[0])
    seen = []
    for _, city in found_positions:
        if city not in seen:
            seen.append(city)
    return seen
