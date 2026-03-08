#!/usr/bin/env bash
# Production startup script
# Runs BOTH the Telegram Bot (background) and the FastAPI Uvicorn Server (foreground)

# Ensure we are in the right directory
cd "$(dirname "$0")/.." || exit 1

echo "Starting OpenClaw Travel Agent [PRODUCTION MODE]"

# Start the Telegram Bot in the background
echo "-> Starting Telegram Bot Process..."
python3 -m bot.telegram_bot &
BOT_PID=$!

# Start the FastAPI Webhook / OpenClaw API Server in the foreground
echo "-> Starting FastAPI Webhook Server..."
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# If Uvicorn dies/stops, kill the bot too
kill $BOT_PID
echo "All processes stopped."
