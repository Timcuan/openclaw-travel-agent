"""
Payment Webhook API.

Receives notifications from the Payment Gateway (or our own simulation)
when a payment is completed.
Updates booking status and triggers ticket issuance.

File: api/payment_hook.py
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from utils.logger import logger
from services.ticketing import issue_ticket

router = APIRouter(prefix="/payment", tags=["Payment"])

class WebhookPayload(BaseModel):
    booking_id: str
    amount_paid: float
    method: str
    status: str
    mock_transaction_id: str


@router.post("/webhook")
async def payment_webhook(payload: WebhookPayload, request: Request):
    """
    Webhook receiver for payment confirmations.
    """
    logger.info(f"[PaymentWebhook] Received {payload.status} for {payload.booking_id}")

    if payload.status != "success":
        return {"status": "ignored", "reason": f"Status is {payload.status}"}

    # 1. Look up booking and update status
    # In a real app we would verify signatures and idempotency here.
    from database.db import AsyncSessionLocal
    from database.models import Booking, BookingStatus
    from sqlalchemy import select

    updated = False
    
    # Try DB first
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Booking).where(Booking.id == payload.booking_id)
            result = await session.execute(stmt)
            booking = result.scalar_one_or_none()
            
            if booking:
                booking.status = BookingStatus.paid
                await session.commit()
                updated = True
    except Exception as e:
        logger.error(f"[PaymentWebhook] DB error: {e}")

    # Fallback to in-memory if DB update didn't happen (e.g. SQLite locking or in-memory mode)
        from services.booking_manager import _in_memory_bookings
        
        # In-memory bookings are stored with booking_id as the key
        if payload.booking_id in _in_memory_bookings:
            mem_booking = _in_memory_bookings[payload.booking_id]
            mem_booking["status"] = "paid"
            updated = True

    if not updated:
        logger.warning(f"[PaymentWebhook] Booking {payload.booking_id} not found in DB or memory")
        raise HTTPException(status_code=404, detail="Booking not found")

    # 2. Issue the ticket and notify user
    import asyncio
    asyncio.create_task(issue_ticket(payload.booking_id))

    return {"status": "ok", "message": "Payment confirmed, ticketing started"}
