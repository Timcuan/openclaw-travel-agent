"""
Mock Payment Gateway.

Simulates generating a payment link (like Midtrans SNAP or Xendit Invoice)
and automatically hitting our own webhook after a short delay to simulate
the user actually paying.

File: services/payment_gateway.py
"""
import asyncio
import os
import httpx
from utils.logger import logger

# The base URL of our own API, used by the background task to hit the webhook.
# If running in Docker, it should be the service name or localhost.
LOCAL_API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

async def create_payment_link(booking_id: str, amount: float, method: str) -> str:
    """
    Generate a mock payment URL and trigger a background payment simulation.
    """
    # 1. Generate a mock URL
    import uuid
    token = str(uuid.uuid4())[:8]
    payment_url = f"https://pay.openclaw.local/checkout/{booking_id}/{token}"

    logger.info(f"[PaymentGateway] Generated mock link for {booking_id}: {payment_url}")

    # 2. Fire and forget the simulation
    # In a real app, the user scans/clicks the link and pays.
    # Here, we just wait 10 seconds and call our own webhook.
    asyncio.create_task(_simulate_user_payment(booking_id, amount, method))

    return payment_url


async def _simulate_user_payment(booking_id: str, amount: float, method: str):
    """
    Wait 10 seconds, then send a POST request to our /payment/webhook endpoint.
    """
    await asyncio.sleep(10.0)
    logger.info(f"[PaymentGateway] Simulating successful payment for {booking_id}...")

    payload = {
        "booking_id": booking_id,
        "amount_paid": amount,
        "method": method,
        "status": "success",
        "mock_transaction_id": f"TRX-{booking_id[-4:]}"
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{LOCAL_API_URL}/payment/webhook",
                json=payload,
                timeout=10.0
            )
            if resp.status_code == 200:
                logger.info(f"[PaymentGateway] Webhook delivered successfully for {booking_id}")
            else:
                logger.error(f"[PaymentGateway] Webhook failed {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"[PaymentGateway] Failed to reach local webhook: {e}")
