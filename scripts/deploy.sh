#!/usr/bin/env bash
# ============================================================
#  deploy.sh – Deploy OpenClaw Travel Agent on VPS
#
#  Run once on the VPS after git clone:
#    curl -sO https://raw.githubusercontent.com/<user>/<repo>/main/scripts/deploy.sh
#    chmod +x deploy.sh && sudo bash deploy.sh
#
#  Or after git pull:
#    bash scripts/deploy.sh
# ============================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$PROJECT_DIR")"  # go up from scripts/
LOG_DIR="$PROJECT_DIR/logs"
SERVICE_FILE="$PROJECT_DIR/deploy/openclaw-travel-agent.service"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

header() { echo -e "\n${CYAN}▶ $*${NC}"; }
ok()     { echo -e "  ${GREEN}✅ $*${NC}"; }
warn()   { echo -e "  ${YELLOW}⚠️  $*${NC}"; }

header "OpenClaw Travel Agent – VPS Deploy"
echo "  Project: $PROJECT_DIR"
echo "  Date:    $(date '+%Y-%m-%d %H:%M:%S')"

# ── 1. Check OS ───────────────────────────────────────────────────────────────
header "1/7  System check"
if [[ "$(uname)" != "Linux" ]]; then
    warn "This script is designed for Linux VPS. Detected: $(uname)"
fi
ok "OS: $(uname -srm)"

# ── 2. Install system dependencies ───────────────────────────────────────────
header "2/7  Installing dependencies"
if command -v apt-get &>/dev/null; then
    apt-get update -qq
    apt-get install -y -qq python3.11 python3.11-venv python3-pip git curl docker.io docker-compose
    ok "apt packages installed"
elif command -v yum &>/dev/null; then
    yum install -y -q python3.11 git curl docker
    ok "yum packages installed"
fi

# ── 3. Python venv ────────────────────────────────────────────────────────────
header "3/7  Python virtual environment"
cd "$PROJECT_DIR"
if [ ! -d venv ]; then
    python3.11 -m venv venv
    ok "venv created"
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
ok "Dependencies installed"

# ── 4. Environment file ───────────────────────────────────────────────────────
header "4/7  Environment configuration"
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    warn ".env created from example. Edit it now:"
    warn "  nano $PROJECT_DIR/.env"
    warn "  Required: GROQ_API_KEY и TELEGRAM_BOT_TOKEN"
else
    ok ".env already exists"
fi

# ── 5. Logs directory ─────────────────────────────────────────────────────────
header "5/7  Directories"
mkdir -p "$LOG_DIR"
ok "logs/ ready"

# ── 6. Docker Compose (preferred on VPS) ──────────────────────────────────────
header "6/7  Docker services"
if command -v docker-compose &>/dev/null || command -v docker &>/dev/null; then
    cd "$PROJECT_DIR"
    docker-compose pull --quiet 2>/dev/null || true
    docker-compose up -d --build
    ok "Docker containers started"
    echo ""
    docker-compose ps
else
    # Fallback: systemd service
    warn "Docker not found. Installing systemd service instead..."
    if [ -f "$SERVICE_FILE" ] && command -v systemctl &>/dev/null; then
        # Update paths in service file
        PYTHON_PATH="$PROJECT_DIR/venv/bin/python"
        sed "s|/opt/openclaw-travel-agent|$PROJECT_DIR|g" "$SERVICE_FILE" | \
            sed "s|/opt/openclaw-travel-agent/venv/bin/python|$PYTHON_PATH|g" \
            > /etc/systemd/system/openclaw-travel-agent.service

        # Create log dir with right perms
        mkdir -p /var/log/openclaw
        systemctl daemon-reload
        systemctl enable openclaw-travel-agent
        systemctl restart openclaw-travel-agent
        ok "systemd service enabled and started"
        systemctl status openclaw-travel-agent --no-pager
    else
        # Last resort: watchdog
        warn "systemd not available. Starting watchdog..."
        nohup bash "$PROJECT_DIR/scripts/keep-alive.sh" >> "$LOG_DIR/bot.log" 2>&1 &
        ok "Watchdog started (PID $!)"
    fi
fi

# ── 7. Health check ───────────────────────────────────────────────────────────
header "7/7  Health check"
sleep 5
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    ok "API is healthy → http://localhost:8000/health"
    curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || true
else
    warn "API not yet reachable. Wait 15s then: curl http://localhost:8000/health"
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗"
echo -e "║  🚀  OpenClaw Travel Agent deployed!           ║"
echo -e "╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Bot logs:     docker-compose logs -f telegram_bot"
echo "  API docs:     http://<your-vps-ip>:8000/docs"
echo "  Health:       http://<your-vps-ip>:8000/health"
echo "  Stop:         docker-compose down"
echo ""
