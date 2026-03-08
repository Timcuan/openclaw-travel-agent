"""
WhatsApp Cloud API bot.

Webhook receiver for incoming WhatsApp messages, routed through
the OpenClaw agent. Sends replies via WhatsApp Cloud API.

Webhook endpoint: POST /whatsapp/webhook
Verify endpoint:  GET  /whatsapp/webhook
"""
import os
import httpx
from utils.logger import logger

WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "openclaw_verify")
WA_API_VERSION = "v19.0"
WA_BASE_URL = f"https://graph.facebook.com/{WA_API_VERSION}"
TIMEOUT = 15


async def send_whatsapp_message(to: str, text: str) -> bool:
    """
    Send a text message via WhatsApp Cloud API.

    Args:
        to: Recipient phone number in E.164 format (e.g. "628123456789").
        text: Message text (plain text, no Markdown).

    Returns:
        True on success.
    """
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        logger.warning("[WhatsApp] Missing credentials – message not sent")
        return False

    url = f"{WA_BASE_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": _strip_markdown(text)},
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            logger.info(f"[WhatsApp] Message sent to {to}")
            return True
    except Exception as e:
        logger.error(f"[WhatsApp] Failed to send message to {to}: {e}")
        return False


def verify_webhook(mode: str, token: str, challenge: str) -> str | None:
    """
    Verify WhatsApp webhook subscription.

    Returns challenge string if verified, None otherwise.
    """
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        logger.info("[WhatsApp] Webhook verified successfully")
        return challenge
    logger.warning("[WhatsApp] Webhook verification failed")
    return None


def extract_message(payload: dict) -> tuple[str | None, str | None]:
    """
    Extract sender phone and message text from WhatsApp webhook payload.

    Returns:
        (sender_phone, message_text) or (None, None) if not a text message.
    """
    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return None, None

        msg = messages[0]
        if msg.get("type") != "text":
            return None, None

        from_phone = msg.get("from")
        text = msg.get("text", {}).get("body", "")
        return from_phone, text
    except (IndexError, KeyError, TypeError) as e:
        logger.debug(f"[WhatsApp] Could not extract message: {e}")
        return None, None


def _strip_markdown(text: str) -> str:
    """Remove Markdown formatting for WhatsApp plain text."""
    import re
    text = re.sub(r"\*(.+?)\*", r"\1", text)  # bold
    text = re.sub(r"_(.+?)_", r"\1", text)    # italic
    text = re.sub(r"`(.+?)`", r"\1", text)    # code
    return text
