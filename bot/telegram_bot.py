"""
Telegram Bot – receives messages, routes through OpenClaw agent, replies.

Supports:
- Text messages → search + booking flow
- /start, /reset commands
- Inline formatting with Markdown
"""
import asyncio
import logging
import os

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters,
)
from telegram.constants import ParseMode

from ai.travel_agent import run_agent as _groq_agent
from agent.openclaw_agent import handle_message as _fallback_agent
from utils.logger import logger

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


# Use Groq agent if API key is available, otherwise fallback
async def _dispatch(user_id: str, text: str) -> str:
    try:
        return await _groq_agent(user_id, text)
    except RuntimeError:
        return await _fallback_agent(user_id, text)



async def _start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user_id = str(update.effective_chat.id)
    reply = await _dispatch(user_id, "/start")
    await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)


async def _reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reset command."""
    user_id = str(update.effective_chat.id)
    reply = await _dispatch(user_id, "/reset")
    await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)


async def _pesanan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /pesanan – show booking history."""
    user_id = str(update.effective_chat.id)
    reply = await _dispatch(user_id, "/pesanan")
    await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)


async def _handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all plain text messages."""
    if not update.message or not update.message.text:
        return

    user_id = str(update.effective_chat.id)
    text = update.message.text.strip()

    if not text:
        return

    logger.info(f"[Telegram] user={user_id} msg={text!r}")

    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    try:
        reply = await _dispatch(user_id, text)
        await update.message.reply_text(
            reply,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.exception(f"[Telegram] Error handling message: {e}")
        await update.message.reply_text(
            "❌ Terjadi kesalahan. Silakan coba lagi.",
            parse_mode=ParseMode.MARKDOWN,
        )


def build_application() -> Application:
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in environment.")

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .build()
    )

    app.add_handler(CommandHandler("start", _start))
    app.add_handler(CommandHandler("reset", _reset))
    app.add_handler(CommandHandler("pesanan", _pesanan))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text))

    return app


def main():
    logger.info("🤖 Starting Telegram bot...")
    app = build_application()
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message"],
    )


if __name__ == "__main__":
    main()
