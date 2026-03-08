"""
Live Midtrans Payment Gateway.

Integrates with Midtrans SNAP API to generate real payment links
where users can pay with GoPay, QRIS, Virtual Accounts (BCA, Mandiri, dll).

File: services/payment_gateway.py
"""
import os
import base64
import httpx
from utils.logger import logger

def _get_midtrans_url() -> str:
    is_prod = os.getenv("MIDTRANS_IS_PRODUCTION", "false").lower() == "true"
    return "https://app.midtrans.com/snap/v1/transactions" if is_prod else "https://app.sandbox.midtrans.com/snap/v1/transactions"

def _get_auth_header() -> dict:
    server_key = os.getenv("MIDTRANS_SERVER_KEY", "")
    auth_string = base64.b64encode(f"{server_key}:".encode('utf-8')).decode('utf-8')
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Basic {auth_string}"
    }

async def create_payment_link(booking_id: str, amount: float, method: str) -> str:
    """
    Call Midtrans SNAP API to create a transaction and get the redirect_url.
    """
    server_key = os.getenv("MIDTRANS_SERVER_KEY")
    if not server_key:
        logger.warning("[PaymentGateway] MIDTRANS_SERVER_KEY not set! Falling back to simulated loopback.")
        return f"https://pay.openclaw.local/checkout/{booking_id}/MISSING_KEY"

    url = _get_midtrans_url()
    headers = _get_auth_header()
    
    payload = {
        "transaction_details": {
            "order_id": booking_id,
            "gross_amount": int(amount)  # Midtrans requires integer for IDR
        },
        "customer_details": {
            "first_name": "Traveler", # We could pass real name
            "email": "traveler@openclaw.local",
            "phone": "08123456789"
        }
        # Optionally, we can define 'enabled_payments' based on the 'method' argument
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=10.0)
            data = resp.json()
            
            if resp.status_code == 201:
                logger.info(f"[PaymentGateway] Midtrans SNAP link created for {booking_id}")
                return data.get("redirect_url", "")
            else:
                logger.error(f"[PaymentGateway] Midtrans API Error {resp.status_code}: {data}")
                return ""
    except Exception as e:
        logger.error(f"[PaymentGateway] Connection to Midtrans failed: {e}")
        return ""
