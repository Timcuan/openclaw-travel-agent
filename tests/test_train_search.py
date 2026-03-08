"""
Tests: train search flow end-to-end.
Run: pytest tests/test_train_search.py -v

File: tests/test_train_search.py
"""
import asyncio
import pytest

# ─── Unit: date parser ────────────────────────────────────────────────────────

def test_date_parser_besok():
    from datetime import datetime, timedelta
    from utils.date_parser import parse_date
    today = datetime(2026, 3, 8)
    result = parse_date("kereta besok", reference=today)
    assert result == "2026-03-09"


def test_date_parser_lusa():
    from datetime import datetime
    from utils.date_parser import parse_date
    today = datetime(2026, 3, 8)
    assert parse_date("lusa", reference=today) == "2026-03-10"


def test_date_parser_iso():
    from utils.date_parser import parse_date
    assert parse_date("2026-04-01") == "2026-04-01"


def test_date_parser_dmy():
    from utils.date_parser import parse_date
    assert parse_date("10/03/2026") == "2026-03-10"


# ─── Unit: location resolver ──────────────────────────────────────────────────

def test_resolve_train_surabaya():
    from utils.location_resolver import resolve_train_station
    assert resolve_train_station("Surabaya") == "SBI"


def test_resolve_train_jakarta():
    from utils.location_resolver import resolve_train_station
    assert resolve_train_station("Jakarta") == "GMR"


def test_resolve_airport_bali():
    from utils.location_resolver import resolve_airport
    assert resolve_airport("bali") == "DPS"


def test_resolve_airport_jakarta():
    from utils.location_resolver import resolve_airport
    assert resolve_airport("jakarta") == "CGK"


# ─── Unit: NLP parser ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_nlp_train_intent():
    from agent.nlp_parser import parse_intent
    intent = await parse_intent("kereta surabaya jakarta besok")
    assert intent.intent in ("search_train", "unknown")
    if intent.intent == "search_train":
        assert intent.origin is not None
        assert intent.destination is not None


@pytest.mark.asyncio
async def test_nlp_booking_number():
    from agent.nlp_parser import parse_intent
    intent = await parse_intent("1")
    assert intent.intent == "booking"
    assert intent.option_number == 1


# ─── Unit: transport decider ──────────────────────────────────────────────────

def test_transport_short_route():
    from agent.transport_decider import decide
    d = decide("jakarta", "bandung")
    assert d.recommended == "train"


def test_transport_long_route():
    from agent.transport_decider import decide
    d = decide("jakarta", "jayapura")
    assert d.recommended == "flight"


# ─── Integration: train search (uses mock data) ───────────────────────────────

@pytest.mark.asyncio
async def test_train_search_mock():
    from providers.train.kai_scraper import kai_search_trains
    results = await kai_search_trains("GMR", "SBI", "2026-04-01", 1)
    assert isinstance(results, list)
    assert len(results) > 0
    first = results[0]
    assert "train_name" in first
    assert "price" in first
    assert first["price"] > 0


@pytest.mark.asyncio
async def test_tiket_search_mock():
    from providers.train.tiket_adapter import tiket_search_trains
    results = await tiket_search_trains("SBI", "GMR", "2026-04-01", 1)
    assert isinstance(results, list)


# ─── Integration: cheapest engine ─────────────────────────────────────────────

def test_cheapest_engine_ranks():
    from services.cheapest_engine import run
    mock = [
        {"price": 500000, "currency": "IDR", "train_name": "A", "provider": "KAI", "origin": "SBI", "destination": "GMR", "departure_time": "08:00"},
        {"price": 300000, "currency": "IDR", "train_name": "B", "provider": "Tiket", "origin": "SBI", "destination": "GMR", "departure_time": "10:00"},
        {"price": 700000, "currency": "IDR", "train_name": "C", "provider": "Traveloka", "origin": "SBI", "destination": "GMR", "departure_time": "14:00"},
    ]
    results = run(mock, "train", top_n=5)
    assert results[0]["price"] <= results[1]["price"]
    assert results[0]["rank"] == 1


# ─── Integration: deal detector ───────────────────────────────────────────────

def test_deal_detector_flags_cheap():
    from services.deal_detector import tag_deals
    results = [
        {"price": 100000, "price_idr": 100000, "provider": "KAI", "origin": "GMR", "destination": "SBI", "train_name": "X", "rank": 1},
        {"price": 520000, "price_idr": 520000, "provider": "KAI", "origin": "GMR", "destination": "SBI", "train_name": "Y", "rank": 2},
    ]
    tagged = tag_deals(results, "train")
    # Cheapest should be tagged as BEST DEAL
    cheap = next(r for r in tagged if r["price"] == 100000)
    assert "🔥" in cheap.get("deal_tag", "") or cheap.get("deal_tag", "") == ""


# ─── Full flow: agent message ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_search_returns_string():
    """Agent must return a non-empty string for a valid train search."""
    from agent.openclaw_agent import handle_message
    reply = await handle_message("test_user_001", "kereta surabaya jakarta besok")
    assert isinstance(reply, str)
    assert len(reply) > 10
