"""
Booking Manager – persists booking requests and generates order summaries.

Flow:
  1. User selects an offer (rank number)
  2. Agent collects passenger info (via session_manager)
  3. booking_manager.create_booking() persists to DB + returns order dict
  4. Agent formats confirmation message

File: services/booking_manager.py
"""
import uuid
from datetime import datetime
from typing import Optional
from utils.logger import logger

# Try to use the database; fall back to in-memory if DB is unavailable
_in_memory_bookings: dict[str, dict] = {}


async def create_booking(
    user_id: str,
    travel_type: str,
    offer: dict,
    passenger_name: str,
    passenger_id: str = "",
    passenger_phone: str = "",
    payment_method: str = "",
) -> dict:
    """
    Persist a booking and return the order dict.

    Args:
        user_id: Platform user identifier.
        travel_type: 'train' | 'flight' | 'hotel'.
        offer: Selected offer dict from search results.
        passenger_name: Full name.
        passenger_id: KTP / NIK (optional).
        passenger_phone: Phone number (optional).
        payment_method: Selected payment method string.

    Returns:
        Order dict with booking_id and summary.
    """
    booking_id = f"OCL-{str(uuid.uuid4())[:8].upper()}"
    price = offer.get("price", 0) or offer.get("price_per_night", 0)

    order = {
        "booking_id": booking_id,
        "user_id": user_id,
        "travel_type": travel_type,
        "status": "pending_payment",
        "passenger_name": passenger_name,
        "passenger_id": passenger_id,
        "passenger_phone": passenger_phone,
        "payment_method": payment_method,
        "price": price,
        "currency": "IDR",
        "offer": offer,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": None,
    }

    # DB persistence (async, non-blocking – skip if DB unavailable)
    try:
        await _persist_to_db(order)
    except Exception as e:
        logger.warning(f"[BookingManager] DB persist failed (using in-memory): {e}")
        _in_memory_bookings[booking_id] = order

    logger.info(f"[BookingManager] Created booking {booking_id} for user {user_id}")
    return order


async def get_booking(booking_id: str) -> Optional[dict]:
    """Retrieve a booking by ID."""
    # Try DB first
    try:
        return await _get_from_db(booking_id)
    except Exception:
        pass
    return _in_memory_bookings.get(booking_id)


async def list_user_bookings(user_id: str, limit: int = 5) -> list[dict]:
    """Return recent bookings for a user."""
    try:
        return await _list_from_db(user_id, limit)
    except Exception:
        return [b for b in _in_memory_bookings.values() if b["user_id"] == user_id][-limit:]


def format_order_confirmation(order: dict) -> str:
    """Format a booking confirmation message (Markdown)."""
    from services.cheapest_engine import format_price
    offer = order.get("offer", {})
    travel_type = order.get("travel_type", "")
    price_str = format_price(order.get("price", 0))
    booking_id = order.get("booking_id", "?")
    name = order.get("passenger_name", "")
    payment = order.get("payment_method", "")

    offer_line = _offer_one_liner(travel_type, offer)

    return (
        "🎉 *Pesanan Berhasil Dibuat!*\n\n"
        f"📋 Order ID: `{booking_id}`\n"
        f"{offer_line}\n"
        f"👤 Nama: *{name}*\n"
        f"💳 Pembayaran: *{payment}*\n"
        f"💰 Total: *{price_str}*\n\n"
        "⏳ Selesaikan pembayaran dalam *30 menit*.\n"
        "Konfirmasi akan dikirim via pesan ini. 🙏\n\n"
        "_Ketik pencarian baru untuk mulai lagi._"
    )


def _offer_one_liner(travel_type: str, offer: dict) -> str:
    if travel_type == "train":
        return (
            f"🚂 *{offer.get('train_name','?')}*  "
            f"{offer.get('departure_time','--')} → {offer.get('arrival_time','--')}\n"
            f"   {offer.get('origin','')} → {offer.get('destination','')}"
        )
    if travel_type == "flight":
        dep = (offer.get("departure_time","")[-5:]) or "--:--"
        arr = (offer.get("arrival_time","")[-5:]) or "--:--"
        return (
            f"✈️ *{offer.get('airline','?')} {offer.get('flight_number','')}*  "
            f"{dep} → {arr}\n"
            f"   {offer.get('origin','')} → {offer.get('destination','')}"
        )
    if travel_type == "hotel":
        return (
            f"🏨 *{offer.get('hotel_name','?')}*\n"
            f"   {offer.get('check_in','')} → {offer.get('check_out','')}"
        )
    return ""


# ─── DB helpers (async SQLAlchemy) ────────────────────────────────────────────

async def _persist_to_db(order: dict):
    from database.db import AsyncSessionLocal
    from database.models import Booking, TravelType as DBTravelType, BookingStatus
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        booking = Booking(
            travel_type=DBTravelType(order["travel_type"]),
            status=BookingStatus.pending,
            passenger_name=order["passenger_name"],
            passenger_id_number=order.get("passenger_id"),
            passenger_phone=order.get("passenger_phone"),
            provider=order["offer"].get("provider"),
            origin=order["offer"].get("origin"),
            destination=order["offer"].get("destination"),
            travel_date=order["offer"].get("date"),
            departure_time=order["offer"].get("departure_time"),
            arrival_time=order["offer"].get("arrival_time"),
            train_name=order["offer"].get("train_name"),
            flight_number=order["offer"].get("flight_number"),
            hotel_name=order["offer"].get("hotel_name"),
            check_in=order["offer"].get("check_in"),
            check_out=order["offer"].get("check_out"),
            price=order["price"],
            currency="IDR",
            offer_snapshot=order["offer"],
        )
        session.add(booking)
        await session.commit()
        order["db_booking_id"] = str(booking.id)


async def _get_from_db(booking_id: str) -> Optional[dict]:
    return None  # implement lookup by order code if needed


async def _list_from_db(user_id: str, limit: int) -> list[dict]:
    return []  # full implementation uses SQLAlchemy JOIN on User
