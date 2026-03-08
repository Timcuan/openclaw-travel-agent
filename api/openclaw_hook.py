"""
OpenClaw Hook – FastAPI router for OpenClaw skill integration.

Endpoints exposed for the OpenClaw agent to call:
  GET  /openclaw/status     – health + available tools list
  POST /openclaw/search     – unified natural-language travel search
  POST /openclaw/book       – start booking flow for a selected result
  GET  /openclaw/history    – get booking history for a user

All responses are JSON in the OpenClaw tool-result schema.

File: api/openclaw_hook.py
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from utils.logger import logger

router = APIRouter(prefix="/openclaw", tags=["OpenClaw"])

API_VERSION = "v4"
TODAY = lambda: datetime.now().strftime("%Y-%m-%d")


# ─── Schemas ──────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., description="Natural language query (Indonesian or English)", example="kereta surabaya jakarta besok")
    type: Optional[Literal["train", "flight", "hotel"]] = Field(
        None, description="Force a specific travel type. Leave empty for auto-detect."
    )
    user_id: str = Field(default="openclaw_user", description="Caller identity for session tracking")


class BookRequest(BaseModel):
    user_id: str = Field(..., example="openclaw_user")
    option: int = Field(..., ge=1, le=9, description="Rank of the result to book (1-based)")


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/status")
async def openclaw_status():
    """
    Health check for the OpenClaw skill.
    Returns available tools and today's date for context.
    """
    groq_ready = bool(os.getenv("GROQ_API_KEY"))
    return {
        "status": "ok",
        "version": API_VERSION,
        "today": TODAY(),
        "llm": "groq/llama-3.3-70b-versatile" if groq_ready else "rule-based",
        "tools": ["search_train", "search_flight", "search_hotel", "book_ticket", "check_booking"],
        "providers": {
            "train":  ["KAI", "Tiket", "Traveloka"],
            "flight": ["Amadeus", "Kiwi", "Skyscanner"],
            "hotel":  ["LiteAPI", "Booking.com", "Agoda"],
        },
        "cache_ttl_minutes": 10,
    }


@router.post("/search")
async def openclaw_search(req: SearchRequest):
    """
    Unified natural-language travel search for the OpenClaw agent.

    Auto-detects travel type (train / flight / hotel) unless `type` is set.
    Returns formatted Markdown message + structured result list.
    """
    logger.info(f"[OpenClawHook] search user={req.user_id!r} type={req.type!r} query={req.query!r}")

    # Parse intent from natural language
    from agent.nlp_parser import parse_intent
    intent = await parse_intent(req.query)

    travel_type = req.type or _intent_to_type(intent.intent)

    if not travel_type:
        return {
            "ok": False,
            "message": (
                "Tidak mengenali jenis perjalanan. Coba:\n"
                "• `kereta surabaya jakarta besok`\n"
                "• `pesawat bali jakarta`\n"
                "• `hotel bandung 2 malam`"
            ),
            "travel_type": None,
            "results": [],
        }

    try:
        results, message = await _run_search(req.user_id, travel_type, intent)
        return {
            "ok": True,
            "travel_type": travel_type,
            "count": len(results),
            "results": results,
            "message": message,
            "query_parsed": {
                "origin": intent.origin,
                "destination": intent.destination,
                "city": intent.city,
                "date": intent.date,
                "check_in": intent.check_in,
                "check_out": intent.check_out,
                "passengers": intent.passengers,
            },
        }
    except Exception as e:
        logger.error(f"[OpenClawHook] Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/book")
async def openclaw_book(req: BookRequest):
    """
    Start the booking process for a selected search result.

    The OpenClaw agent calls this when the user picks an option number.
    Returns the next prompt for the agent to relay to the user.
    """
    import services.session_manager as sm
    from services.cheapest_engine import format_price

    logger.info(f"[OpenClawHook] book user={req.user_id!r} option={req.option}")

    offer = await sm.get_selected_offer(req.user_id, req.option)
    if not offer:
        _, results = await sm.get_results(req.user_id)
        raise HTTPException(
            status_code=404,
            detail=f"Option {req.option} not found. Available: 1–{len(results)}"
        )

    await sm.update_session(
        req.user_id,
        stage="awaiting_name",
        selected_option=req.option,
        selected_offer=offer,
    )

    price = offer.get("price_idr") or offer.get("price") or 0
    return {
        "ok": True,
        "stage": "awaiting_name",
        "selected": offer,
        "price_formatted": format_price(price),
        "next_prompt": (
            f"✅ Pilihan diterima!\n\n"
            f"Harga: *{format_price(price)}*\n\n"
            f"Silakan masukkan nama penumpang lengkap (sesuai KTP):"
        ),
    }


@router.get("/history/{user_id}")
async def openclaw_history(user_id: str):
    """Return booking history for a user."""
    from services.booking_manager import get_user_bookings
    bookings = await get_user_bookings(user_id)
    return {
        "ok": True,
        "user_id": user_id,
        "count": len(bookings),
        "bookings": bookings,
    }


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _intent_to_type(intent: str) -> Optional[str]:
    if intent == "search_train":  return "train"
    if intent == "search_flight": return "flight"
    if intent == "search_hotel":  return "hotel"
    return None


async def _run_search(user_id: str, travel_type: str, intent) -> tuple[list, str]:
    """Execute the search pipeline and return (results, markdown_message)."""
    from services.provider_manager import run_search
    from services.cheapest_engine import run as cheapest_run, format_results
    from services.deal_detector import tag_deals
    from utils.location_resolver import resolve_train_station, resolve_airport, resolve_hotel_city
    import services.session_manager as sm
    import cache.search_cache as sc

    if travel_type == "train":
        origin = resolve_train_station(intent.origin or "") or (intent.origin or "GMR")
        dest   = resolve_train_station(intent.destination or "") or (intent.destination or "SBI")
        date   = intent.date or TODAY()
        cache_key = sc.train_key(origin, dest, date)

        cached = await sc.get(cache_key)
        if cached:
            return cached, format_results("train", cached)

        norm = await run_search("train", {"origin": origin, "destination": dest, "date": date, "passengers": intent.passengers})
        raw = [r.to_dict() for r in norm]
        results = tag_deals(cheapest_run(raw, "train", top_n=5), "train")
        await sc.set(cache_key, results)
        await sm.store_results(user_id, "train", results)
        return results, format_results("train", results)

    if travel_type == "flight":
        origin = resolve_airport(intent.origin or "") or (intent.origin or "CGK")
        dest   = resolve_airport(intent.destination or "") or (intent.destination or "DPS")
        date   = intent.date or TODAY()
        cache_key = sc.flight_key(origin, dest, date)

        cached = await sc.get(cache_key)
        if cached:
            return cached, format_results("flight", cached)

        norm = await run_search("flight", {"origin": origin, "destination": dest, "date": date, "passengers": intent.passengers})
        raw = [r.to_dict() for r in norm]
        results = tag_deals(cheapest_run(raw, "flight", top_n=5), "flight")
        await sc.set(cache_key, results)
        await sm.store_results(user_id, "flight", results)
        return results, format_results("flight", results)

    if travel_type == "hotel":
        city     = resolve_hotel_city(intent.city or "") or (intent.city or "Jakarta")
        check_in  = intent.check_in or TODAY()
        check_out = intent.check_out or TODAY()
        cache_key = sc.hotel_key(city, check_in, check_out)

        cached = await sc.get(cache_key)
        if cached:
            return cached, format_results("hotel", cached)

        norm = await run_search("hotel", {"city": city, "check_in": check_in, "check_out": check_out, "adults": intent.passengers, "rooms": intent.rooms})
        raw = [r.to_dict() for r in norm]
        results = tag_deals(cheapest_run(raw, "hotel", top_n=5), "hotel")
        await sc.set(cache_key, results)
        await sm.store_results(user_id, "hotel", results)
        return results, format_results("hotel", results)

    return [], "Jenis perjalanan tidak dikenali."
