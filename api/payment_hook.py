"""
Payment Webhook API.

Receives notifications from Midtrans when a payment is completed.
Verifies the SHA512 signature, updates booking status, and triggers ticket issuance.

File: api/payment_hook.py
"""
import os
import hashlib
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from utils.logger import logger
from services.ticketing import issue_ticket

router = APIRouter(prefix="/payment", tags=["Payment"])

class MidtransWebhookPayload(BaseModel):
    transaction_time: str
    transaction_status: str
    transaction_id: str
    status_message: str
    status_code: str
    signature_key: str
    payment_type: str
    order_id: str
    gross_amount: str
    merchant_id: Optional[str] = None
    fraud_status: Optional[str] = None
    currency: Optional[str] = "IDR"
    
    # We allow extra fields since midtrans sends bank_ids etc.
    model_config = ConfigDict(extra="allow")


def verify_signature(order_id: str, status_code: str, gross_amount: str, signature_key: str) -> bool:
    """Verifies the Midtrans SHA512 signature to ensure the webhook is authentic."""
    server_key = os.getenv("MIDTRANS_SERVER_KEY", "")
    if not server_key:
        logger.warning("[PaymentWebhook] MIDTRANS_SERVER_KEY not set. Bypassing signature verification (INSECURE DEPLOYMENT).")
        return True
        
    payload = f"{order_id}{status_code}{gross_amount}{server_key}"
    calculated_sig = hashlib.sha512(payload.encode('utf-8')).hexdigest()
    
    return calculated_sig == signature_key


@router.post("/webhook")
async def payment_webhook(payload: MidtransWebhookPayload, request: Request, background_tasks: BackgroundTasks):
    """
    Webhook receiver for Midtrans payment confirmations.
    Includes SHA512 verification, idempotency checks and DB row-level locking.
    """
    logger.info(f"[PaymentWebhook] Received {payload.transaction_status} for {payload.order_id}")

    # 1. Verify Authentication Signature
    if not verify_signature(payload.order_id, payload.status_code, payload.gross_amount, payload.signature_key):
        logger.error(f"[PaymentWebhook] Invalid Signature for {payload.order_id}. Possible unauthorized access.")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 2. Check Transaction Status
    # Midtrans uses 'settlement' or 'capture' (for CC) to represent successful paid transactions
    status = payload.transaction_status
    if status not in ["settlement", "capture"]:
        logger.info(f"[PaymentWebhook] Status is {status}, ignoring (waiting for settlement).")
        return {"status": "ignored", "reason": f"Status is {status}"}
        
    # Extra check if fraud status is challenge (need manual review on Midtrans dash)
    if status == "capture" and payload.fraud_status == "challenge":
        return {"status": "ignored", "reason": "fraud_status is challenge"}

    # 3. Look up booking and update status
    from database.db import AsyncSessionLocal
    from database.models import Booking, BookingStatus
    from sqlalchemy import select

    updated = False
    
    # Try DB first
    try:
        async with AsyncSessionLocal() as session:
            # with_for_update() locks the row to prevent race conditions during concurrent webhooks
            stmt = select(Booking).where(Booking.id == payload.order_id).with_for_update()
            result = await session.execute(stmt)
            booking = result.scalar_one_or_none()
            
            if booking:
                # Idempotency check: if already paid or issued, ignore
                if booking.status in (BookingStatus.paid, BookingStatus.issued):
                    logger.info(f"[PaymentWebhook] Booking {payload.order_id} already {booking.status}, ignoring webhook.")
                    return {"status": "ok", "message": "Already processed"}
                    
                booking.status = BookingStatus.paid
                await session.commit()
                updated = True
    except Exception as e:
        logger.error(f"[PaymentWebhook] DB error: {e}")

    # Fallback to in-memory if DB update didn't happen (e.g. SQLite locking or in-memory mode)
    if not updated:
        from services.booking_manager import get_booking, _in_memory_bookings
        
        # If the booking ID is the short OC prefix (in-memory case)
        mem_booking = await get_booking(payload.order_id)
        
        if not mem_booking:
            for oc_id, b in _in_memory_bookings.items():
                if b.get("db_booking_id") == str(payload.order_id):
                    mem_booking = b
                    payload.order_id = oc_id
                    break
                    
        if mem_booking:
            # Check idempotency for in-memory
            if mem_booking.get("status") in ("paid", "issued"):
                return {"status": "ok", "message": "Already processed"}
                
            mem_booking["status"] = "paid"
            updated = True

    if not updated:
        logger.warning(f"[PaymentWebhook] Booking {payload.order_id} not found in DB or memory")
        raise HTTPException(status_code=404, detail="Booking not found")

    # 4. Issue the ticket and notify user gracefully
    background_tasks.add_task(issue_ticket, payload.order_id)

    return {"status": "ok", "message": "Payment confirmed, ticketing started"}
