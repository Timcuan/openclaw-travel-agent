"""
Ticketing Service.

Once a booking is paid, this service "issues" the ticket (generates a PNR)
and sends the E-Ticket directly to the user via Telegram.

File: services/ticketing.py
"""
import uuid
import os
from utils.logger import logger
from database.db import AsyncSessionLocal
from database.models import Booking, BookingStatus, Ticket

async def issue_ticket(booking_id: str):
    """
    Generate an e-ticket for a paid booking, update DB, and notify the user.
    """
    logger.info(f"[Ticketing] Issuing ticket for {booking_id}...")

    pnr_code = str(uuid.uuid4())[:6].upper()

    user_id = None
    platform = None
    platform_user_id = None
    travel_type = None
    offer = None
    passenger = None
    db_id = None

    # 1. Update DB: create ticket and change booking status to issued
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload
        
        stmt = select(Booking).options(joinedload(Booking.user)).where(Booking.id == booking_id).with_for_update()
        result = await session.execute(stmt)
        booking = result.scalar_one_or_none()

        if booking:
            # Idempotency check:
            if booking.status == BookingStatus.issued:
                logger.info(f"[Ticketing] Booking {booking_id} already issued, skipping.")
                return
                
            booking.status = BookingStatus.issued
            
            ticket = Ticket(
                booking_id=booking.id,
                ticket_code=pnr_code,
                raw_data={"pnr": pnr_code, "note": "Mock generated ticket"}
            )
            session.add(ticket)
            
            user_id = str(booking.user_id)
            if booking.user:
                platform = booking.user.platform.value
                platform_user_id = booking.user.platform_user_id
            
            travel_type = booking.travel_type.value
            offer = booking.offer_snapshot
            passenger = booking.passenger_name
            db_id = booking.id
            
            await session.commit()
        else:
            logger.warning(f"[Ticketing] DB Booking {booking_id} not found, falling back to in-memory fetch")

    # If DB failed or absent, fetch from in-memory (BookingManager tracking map)
    if not offer:
        from services.booking_manager import get_booking
        # If the booking ID was the short OC prefix instead of UUID (in-memory case)
        mem_booking = await get_booking(booking_id)
        if not mem_booking:
            # Check if it was passed the DB UUID but we only have OC prefix in memory
            for oc_id, b in __import__("services").booking_manager._in_memory_bookings.items():
                if b.get("db_booking_id") == str(booking_id):
                    mem_booking = b
                    booking_id = oc_id
                    break

        if mem_booking:
            mem_booking["status"] = "issued"
            mem_booking["ticket_code"] = pnr_code
            user_id = mem_booking["user_id"]
            travel_type = mem_booking["travel_type"]
            offer = mem_booking["offer"]
            passenger = mem_booking["passenger_name"]
            
            # Since standard memory format uses Telegram ID directly as user_id for simplicity
            platform = "telegram"
            platform_user_id = user_id

    # 2. Build the E-Ticket message
    if not offer:
        logger.error(f"[Ticketing] Could not find order data to issue ticket for {booking_id}")
        return

    msg = _build_eticket(pnr_code, travel_type, offer, passenger)
    
    # 3. Send Notification via Telegram with Resiliency
    if platform == "telegram" and platform_user_id:
        import httpx
        import asyncio
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if token:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            f"https://api.telegram.org/bot{token}/sendMessage",
                            json={
                                "chat_id": platform_user_id,
                                "text": msg,
                                "parse_mode": "Markdown",
                                "disable_web_page_preview": True,
                            },
                            timeout=10.0
                        )
                        if resp.status_code == 200:
                            logger.info(f"[Ticketing] E-Ticket {pnr_code} sent to {platform_user_id}")
                            break
                        else:
                            logger.warning(f"[Ticketing] Telegram API error {resp.status_code}: {resp.text}")
                except Exception as e:
                    logger.error(f"[Ticketing] Failed to send Telegram message (Attempt {attempt+1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s
            else:
                logger.error(f"[Ticketing] Exhausted all retries. Failed to deliver E-Ticket {pnr_code} to {platform_user_id}")
    else:
        logger.info(f"[Ticketing] (No Telegram ID found to send ticket directly, likely OpenClaw local user)")


def _build_eticket(pnr: str, type: str, offer: dict, passenger: str) -> str:
    """Format the E-Ticket Markdown message."""
    icon = {"train": "🚂", "flight": "✈️", "hotel": "🏨"}.get(type, "🎫")
    
    lines = [
        f"✅ *PEMBAYARAN DITERIMA*\n",
        f"🎉 *E-TICKET {type.upper()} TERBIT* {icon}\n",
        f"🎫 *KODE BOOKING (PNR) : `{pnr}`*",
        f"👤 Penumpang        : *{passenger}*\n"
    ]
    
    if type == "train":
        lines.append(f"Kereta : {offer.get('train_name')}")
        lines.append(f"Rute   : {offer.get('origin')} → {offer.get('destination')}")
        lines.append(f"Waktu  : {offer.get('date')} | {offer.get('departure_time')} - {offer.get('arrival_time')}")
    elif type == "flight":
        lines.append(f"Maskapai: {offer.get('airline')} {offer.get('flight_number')}")
        lines.append(f"Rute    : {offer.get('origin')} → {offer.get('destination')}")
        lines.append(f"Keberangkatan: {offer.get('date')} {offer.get('departure_time')}")
    elif type == "hotel":
        lines.append(f"Hotel    : {offer.get('hotel_name')}")
        lines.append(f"Check-in : {offer.get('check_in')}")
        lines.append(f"Check-out: {offer.get('check_out')}")
        
    lines.append("\n_Tunjukkan kode PNR ini saat check-in. Terima kasih!_")
    return "\n".join(lines)
