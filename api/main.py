"""
FastAPI main application – OpenClaw Travel Agent v4

Endpoints:
    GET  /health                  – health check
    GET  /openclaw/status         – OpenClaw skill health + tools
    POST /openclaw/search         – natural-language travel search (for OpenClaw)
    POST /openclaw/book           – initiate booking (for OpenClaw)
    GET  /openclaw/history/{uid}  – booking history
    POST /telegram/webhook        – Telegram webhook (alternative to polling)
    POST /search/train            – direct train search
    POST /search/flight           – direct flight search
    POST /search/hotel            – direct hotel search
    GET  /bookings/{user_id}      – list user bookings
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Query, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from typing import Optional

from database.db import init_db
from cache.redis_pool import close_pool as close_redis
from agent.openclaw_agent import handle_message
from api.openclaw_hook import router as openclaw_router
from utils.logger import logger


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 OpenClaw Travel Agent starting up...")
    await init_db()
    yield
    logger.info("🛑 Shutting down...")
    await close_redis()


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="OpenClaw Travel Agent API",
    description="Smart Indonesia domestic travel assistant – trains, flights, hotels.",
    version="4.0.0",
    lifespan=lifespan,
)

# Mount OpenClaw skill router
app.include_router(openclaw_router)


# ─── Schemas ──────────────────────────────────────────────────────────────────

class TrainSearchRequest(BaseModel):
    origin: str = Field(..., example="Surabaya")
    destination: str = Field(..., example="Jakarta")
    date: str = Field(..., example="2026-03-10")
    adult: int = Field(default=1, ge=1, le=9)


class FlightSearchRequest(BaseModel):
    origin: str = Field(..., example="SUB")
    destination: str = Field(..., example="CGK")
    date: str = Field(..., example="2026-03-10")
    adults: int = Field(default=1, ge=1, le=9)


class HotelSearchRequest(BaseModel):
    city: str = Field(..., example="Bandung")
    check_in: str = Field(..., example="2026-03-10")
    check_out: str = Field(..., example="2026-03-11")
    adults: int = Field(default=2, ge=1, le=10)
    rooms: int = Field(default=1, ge=1, le=10)


class NLQueryRequest(BaseModel):
    user_id: str = Field(..., example="user_123")
    text: str = Field(..., example="kereta surabaya jakarta besok")


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "service": "openclaw-travel-agent"}


@app.post("/search/train", tags=["Search"])
async def search_train_endpoint(req: TrainSearchRequest):
    """Search train tickets from all providers, return cheapest 5."""
    from services.train_service import search_train
    results = await search_train(req.origin, req.destination, req.date, req.adult)
    return {"results": results, "count": len(results)}


@app.post("/search/flight", tags=["Search"])
async def search_flight_endpoint(req: FlightSearchRequest):
    """Search flights from all providers, return cheapest 5."""
    from services.flight_service import search_flight
    results = await search_flight(req.origin, req.destination, req.date, req.adults)
    return {"results": results, "count": len(results)}


@app.post("/search/hotel", tags=["Search"])
async def search_hotel_endpoint(req: HotelSearchRequest):
    """Search hotels from all providers, return cheapest 5."""
    from services.hotel_service import search_hotel
    results = await search_hotel(
        req.city, req.check_in, req.check_out, req.adults, req.rooms
    )
    return {"results": results, "count": len(results)}


@app.post("/agent/query", tags=["Agent"])
async def agent_query(req: NLQueryRequest):
    """Send a natural language query through the full agent pipeline."""
    reply = await handle_message(req.user_id, req.text)
    return {"reply": reply}


# ─── Telegram Webhook (alternative to polling) ────────────────────────────────

@app.post("/telegram/webhook", tags=["Telegram"])
async def telegram_webhook(request: Request):
    """
    Telegram webhook endpoint.
    Configure via: https://api.telegram.org/bot{TOKEN}/setWebhook?url=...
    """
    try:
        data = await request.json()
        message = data.get("message") or data.get("edited_message")
        if not message:
            return {"ok": True}

        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "")

        if not chat_id or not text:
            return {"ok": True}

        logger.info(f"[TelegramWebhook] chat={chat_id} text={text!r}")
        reply = await handle_message(chat_id, text)

        # Reply via Telegram API
        import httpx
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if token:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": reply,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": True,
                    },
                )
        return {"ok": True}
    except Exception as e:
        logger.exception(f"[TelegramWebhook] Error: {e}")
        return {"ok": False}


# ─── WhatsApp Webhook (deprecated – handled by OpenClaw natively) ──────────

@app.get("/whatsapp/webhook", tags=["WhatsApp (deprecated)"])
async def whatsapp_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """
    WhatsApp webhook verification.
    NOTE: WhatsApp is now handled natively by OpenClaw.
    This endpoint is kept for backward compatibility only.
    """
    VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "openclaw_verify")
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge or "")
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/whatsapp/webhook", tags=["WhatsApp (deprecated)"])
async def whatsapp_webhook(request: Request):
    """
    WhatsApp messages are now handled by OpenClaw natively.
    This stub accepts payloads to prevent webhook errors but does not process them.
    """
    logger.info("[WhatsApp] Webhook received – WhatsApp is deprecated in favour of OpenClaw.")
    return {"status": "ok", "note": "WhatsApp handled by OpenClaw. Use /openclaw/search instead."}
