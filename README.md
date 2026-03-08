# OpenClaw Travel Agent v4

Smart travel assistant for **Indonesia domestic travel** – Telegram + OpenClaw.  
Searches multiple providers simultaneously and returns the **cheapest options** for trains, flights, and hotels.

---

## Quick Start

```bash
# 1. Clone & configure
git clone <repo>
cd openclaw-travel-agent
cp .env.example .env
# Fill in: GROQ_API_KEY, TELEGRAM_BOT_TOKEN

# 2. Run with Docker (recommended)
docker-compose up --build

# 3. Install OpenClaw skill
bash scripts/install_skill.sh
```

---

## Telegram Bot – Always On

```bash
# Option A: Watchdog script (dev/VPS)
chmod +x scripts/keep-alive.sh
nohup bash scripts/keep-alive.sh >> logs/bot.log 2>&1 &

# Option B: Docker (auto-restart built-in)
docker-compose up -d telegram_bot

# Option C: systemd (Linux production)
sudo cp deploy/openclaw-travel-agent.service /etc/systemd/system/
sudo systemctl enable --now openclaw-travel-agent
sudo systemctl status openclaw-travel-agent
```

---

## OpenClaw Skill Integration

OpenClaw discovers the skill at `~/.openclaw/skills/indonesia-travel/`.  
The skill routes travel queries to our local FastAPI at `localhost:8000`.

### Install
```bash
bash scripts/install_skill.sh
```

### How it works
```
User: "cari kereta surabaya jakarta besok"
  ↓ OpenClaw detects travel keyword → loads indonesia-travel skill
  ↓ Calls POST http://localhost:8000/openclaw/search
  ↓ API returns formatted Markdown + structured results
  ↓ OpenClaw displays results to user
```

### OpenClaw Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/openclaw/status` | Health + available tools |
| POST | `/openclaw/search` | NL travel search (auto-detect type) |
| POST | `/openclaw/book` | Start booking for selected option |
| GET | `/openclaw/history/{user_id}` | Booking history |

---

## Architecture

```
Bot channels:
  Telegram ──→ bot/telegram_bot.py ──→ ai/travel_agent.py (Groq)
                                   └──→ agent/openclaw_agent.py (fallback)

OpenClaw:
  OpenClaw  ──→ POST /openclaw/search
                      ↓
              api/openclaw_hook.py
                      ↓
              provider_manager (parallel search)
                      ↓
              cheapest_engine + deal_detector
                      ↓
              JSON response → OpenClaw formats reply


```

---

## Features

| Feature | Details |
|---|---|
| 🚂 Train | KAI + Tiket + Traveloka, sorted cheapest |
| ✈️ Flight | Amadeus + Kiwi + Skyscanner |
| 🏨 Hotel | LiteAPI + Booking.com + Agoda |
| 🤖 AI | Groq `llama-3.3-70b-versatile` + rule-based fallback |
| � Payment | **Live Midtrans SNAP Integration** (QRIS, VA, GoPay) + Secure Signature Webhook |
| �🔌 OpenClaw | Native skill at `~/.openclaw/skills/indonesia-travel/` |
| 📱 Telegram | E-Ticket direct dispatch + Always-on watchdogs |
| 💾 Cache | Redis (10 min TTL) + in-memory fallback |
| 🔁 Resilient | Postgres transactions locking, HTTPX fallbacks, Idempotent ticket webhooks |

---

## Environment Variables

See `.env.example` for all configurable variables. Minimum required to go live:
```bash
GROQ_API_KEY=gsk_...          # Groq LLM (free tier available)
TELEGRAM_BOT_TOKEN=123:ABC... # From @BotFather

# MIDTRANS LIVE PAYMENT (See Midtrans Dashboard -> Settings -> Access Keys)
MIDTRANS_SERVER_KEY=SB-Mid-server-xxxxxxxxxxxxxx
MIDTRANS_IS_PRODUCTION=false
```

> **Webhook configuration for Midtrans:** Make sure you set your Midtrans Payment Notification URL to `https://<YOUR-DOMAIN>/payment/webhook` so the bot can issue tickets securely.

---

## Tests

```bash
python3.11 -m pytest tests/ -v
# → 27 passed in 0.08s (no Redis, no API keys needed)
```

---

## License
MIT
