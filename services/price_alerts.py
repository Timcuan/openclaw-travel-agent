"""
Price Alerts – Redis-backed price watchlist + background worker.

Users can say: "pantau tiket surabaya jakarta"

System stores a watchlist entry in Redis.
Background worker checks every 6 hours.
If cheaper price found → sends Telegram alert.

File: services/price_alerts.py
"""
import asyncio
import json
import os
from datetime import datetime
from typing import Optional
import httpx

from utils.logger import logger

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHECK_INTERVAL_SEC = 6 * 3600  # 6 hours
WATCHLIST_KEY = "price_alerts:watchlist"
ALERT_TTL = 7 * 24 * 3600  # 7 days


_redis = None


async def _get_redis():
    global _redis
    if _redis is None:
        import redis.asyncio as aioredis
        _redis = await aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    return _redis


# ─── Public API ───────────────────────────────────────────────────────────────

async def add_alert(
    user_id: str,
    travel_type: str,
    origin: str,
    destination: str,
    date: str,
    current_best_price: float,
    city: str = "",
) -> bool:
    """
    Store a price alert watchlist entry.

    Returns True on success.
    """
    alert = {
        "user_id": user_id,
        "travel_type": travel_type,
        "origin": origin,
        "destination": destination,
        "city": city,
        "date": date,
        "baseline_price": current_best_price,
        "created_at": datetime.utcnow().isoformat(),
    }
    key = f"alert:{user_id}:{travel_type}:{origin}:{destination}:{date}"
    try:
        r = await _get_redis()
        await r.setex(key, ALERT_TTL, json.dumps(alert))
        # Add to watchlist set for easy enumeration
        await r.sadd(WATCHLIST_KEY, key)
        logger.info(f"[PriceAlerts] Alert registered: {key}")
        return True
    except Exception as e:
        logger.error(f"[PriceAlerts] Failed to store alert: {e}")
        return False


async def list_alerts(user_id: str) -> list[dict]:
    """Return all active alerts for a user."""
    try:
        r = await _get_redis()
        all_keys = await r.smembers(WATCHLIST_KEY)
        user_keys = [k for k in all_keys if k.startswith(f"alert:{user_id}:")]
        alerts = []
        for key in user_keys:
            raw = await r.get(key)
            if raw:
                alerts.append(json.loads(raw))
        return alerts
    except Exception as e:
        logger.error(f"[PriceAlerts] list_alerts error: {e}")
        return []


async def remove_alert(user_id: str, key: str) -> bool:
    """Remove a specific alert."""
    try:
        r = await _get_redis()
        await r.delete(key)
        await r.srem(WATCHLIST_KEY, key)
        return True
    except Exception as e:
        logger.error(f"[PriceAlerts] remove_alert error: {e}")
        return False


# ─── Background worker ────────────────────────────────────────────────────────

async def run_price_check_worker():
    """
    Background async worker.
    Checks all watchlist items every 6 hours.
    Sends Telegram message when cheaper price found.

    Start this with: asyncio.create_task(run_price_check_worker())
    """
    logger.info("[PriceAlerts] Worker started. Interval: 6h")
    while True:
        await asyncio.sleep(CHECK_INTERVAL_SEC)
        await _check_all_alerts()


async def _check_all_alerts():
    """Check every watchlist item for price drops."""
    try:
        r = await _get_redis()
        all_keys = list(await r.smembers(WATCHLIST_KEY))
        logger.info(f"[PriceAlerts] Checking {len(all_keys)} alerts...")

        for key in all_keys:
            raw = await r.get(key)
            if not raw:
                await r.srem(WATCHLIST_KEY, key)
                continue
            alert = json.loads(raw)
            await _check_single_alert(key, alert)
    except Exception as e:
        logger.error(f"[PriceAlerts] Worker error: {e}")


async def _check_single_alert(key: str, alert: dict):
    from services.multi_search_engine import search
    from services.cheapest_engine import run as cheapest_run, format_price

    try:
        travel_type = alert["travel_type"]
        result = await search(
            travel_type,
            origin=alert.get("origin", ""),
            destination=alert.get("destination", ""),
            date=alert.get("date", ""),
            city=alert.get("city", ""),
            check_in=alert.get("date", ""),
            check_out=alert.get("date", ""),  # simplified
        )
        results = cheapest_run(result["results"], travel_type, top_n=1)

        if not results:
            return

        best = results[0]
        new_price = best.get("price", 0)
        baseline = alert.get("baseline_price", new_price)

        if new_price < baseline * 0.95:  # at least 5% cheaper
            await _send_telegram_alert(alert, new_price, baseline, best, format_price)
            # Update baseline to avoid repeated alerts
            alert["baseline_price"] = new_price
            r = await _get_redis()
            await r.setex(key, ALERT_TTL, json.dumps(alert))

    except Exception as e:
        logger.error(f"[PriceAlerts] Check error for {key}: {e}")


async def _send_telegram_alert(alert: dict, new_price: float, old_price: float, offer: dict, fmt):
    user_id = alert["user_id"]
    travel_type = alert["travel_type"]
    saving = old_price - new_price
    pct = int((saving / old_price) * 100) if old_price else 0

    emoji = {"train": "🚂", "flight": "✈️", "hotel": "🏨"}.get(travel_type, "🎫")
    name = offer.get("train_name") or offer.get("airline") or offer.get("hotel_name") or "?"

    msg = (
        f"🔔 *Harga Turun!* {emoji}\n\n"
        f"*{name}*\n"
        f"{alert.get('origin','')} → {alert.get('destination','') or alert.get('city','')}\n"
        f"📅 {alert.get('date','')}\n\n"
        f"💰 *{fmt(new_price)}*  _(turun {pct}% dari {fmt(old_price)})_\n\n"
        "Segera pesan sebelum harga naik! 🏃"
    )

    if not TELEGRAM_BOT_TOKEN:
        logger.info(f"[PriceAlerts] Would send to {user_id}: {msg[:80]}…")
        return

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": user_id, "text": msg, "parse_mode": "Markdown"},
            )
        logger.info(f"[PriceAlerts] Alert sent to {user_id}")
    except Exception as e:
        logger.error(f"[PriceAlerts] Telegram send error: {e}")
