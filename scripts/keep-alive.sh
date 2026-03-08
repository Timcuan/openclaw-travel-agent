#!/usr/bin/env bash
# ============================================================
#  keep-alive.sh – Telegram Bot watchdog
#
#  Restarts the bot automatically if it exits for any reason.
#  Suitable for dev machines, VPS without systemd, or Docker.
#
#  Usage:
#    chmod +x scripts/keep-alive.sh
#    nohup bash scripts/keep-alive.sh >> logs/bot.log 2>&1 &
#
#  Stop:
#    kill $(cat /tmp/openclaw_bot.pid)
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="/tmp/openclaw_bot.pid"
LOG_FILE="$PROJECT_DIR/logs/bot.log"
PYTHON="$(command -v python3 || command -v python)"
RESTART_DELAY=5     # seconds before restart
MAX_RESTARTS=0      # 0 = infinite

echo "$$" > "$PID_FILE"
mkdir -p "$PROJECT_DIR/logs"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "🚀 OpenClaw Telegram Bot watchdog started (PID $$)"
log "   Project: $PROJECT_DIR"
log "   Log:     $LOG_FILE"

restarts=0
while true; do
    log "--- Starting Telegram bot (restart #$restarts) ---"

    cd "$PROJECT_DIR"
    # Load .env if it exists
    if [ -f .env ]; then
        set -a && source .env && set +a
    fi

    # Run bot; capture exit code
    $PYTHON -m bot.telegram_bot >> "$LOG_FILE" 2>&1
    EXIT_CODE=$?

    log "⚠️  Bot exited with code $EXIT_CODE"

    restarts=$((restarts + 1))
    if [ "$MAX_RESTARTS" -gt 0 ] && [ "$restarts" -ge "$MAX_RESTARTS" ]; then
        log "❌ Max restarts ($MAX_RESTARTS) reached. Stopping watchdog."
        rm -f "$PID_FILE"
        exit 1
    fi

    log "⏳ Restarting in ${RESTART_DELAY}s... (total restarts: $restarts)"
    sleep "$RESTART_DELAY"
done
