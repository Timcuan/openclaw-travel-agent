<div align="center">
  <img src="https://raw.githubusercontent.com/OpenClaw/openclaw/main/assets/logo.png" alt="OpenClaw Logo" width="120" />
  <h1>OpenClaw Travel Agent v4</h1>
  <p><b>Super-Powered Autonomous AI Travel Assistant for Indonesia 🇮🇩</b></p>
  
  [![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-00a393.svg)](https://fastapi.tiangolo.com)
  [![Midtrans](https://img.shields.io/badge/Payment-Midtrans--Live-blueviolet.svg)](https://midtrans.com)
  [![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

  <p>
    An intelligent multi-platform agent that searches <b>Trains, Flights, and Hotels</b> simultaneously across multiple popular Indonesian providers (KAI, Tiket, Traveloka, Agoda, Booking.com, etc.), finds the absolute cheapest deals, and executes live transactions instantly.
  </p>
</div>

---

## ⚡ Core Features

- 🧠 **Groq Llama-3.3 Powered Intent Engine**: Understands messy natural Indonesian language (*"Cariin tiket sby-jkt bsk pagi donk yg murah"*).
- ✈️ **Multi-Concurrent Aggregator**: Hits KAI, Traveloka, Skyscanner, Agoda, and more simultaneously using API clients and Playwright fallback scrapers.
- 💳 **Live Midtrans Payments**: End-to-End dynamic checkout via **QRIS, GoPay, dan Virtual Account** directly inside Telegram chat. Includes scannable QR Barcodes for PC users.
- 🎟 **E-Ticket Dispatcher**: Auto-generates PNRs and sends beautiful E-Tickets via Telegram the second a payment clears the bank webhook.
- 🛡 **Battle-Tested Infrastructure**: Features PostgreSQL connection pooling, `systemd` dual-core Daemon (API + Bot runtime), memory leak guards, and network timeout resistance for 24/7 uptime.

---

## 🏗 Architecture Blueprint

The system consists of two main gateways (Telegram & Native OpenClaw), an Intelligent AI Router, a Concurrent Scraping Engine, and a Secure Payment Pipeline.

```mermaid
graph TD
    %% Users
    U_TG[📱 Telegram User]
    U_OC[💻 OpenClaw CLI/App]

    %% Gateways
    subgraph Gateways [Entry Points]
        TG_BOT((Telegram Bot))
        OC_HOOK(FastAPI Webhook)
    end

    %% Brain
    subgraph Intelligence [AI & NLP]
        GROQ[Groq Llama 3.3]
        FALLBACK[Regex/Rule Fallback]
    end

    %% Core Flow
    subgraph Core [Travel Engine]
        ROUTER{Smart Router}
        CHEAPEST[Deal Detector & Ranker]
        
        AGGREGATOR(Parallel Multi-Search)
        
        subgraph Providers
            TR[🚂 KAI, Tiket, Traveloka]
            FL[✈️ Amadeus, Kiwi, Skyscanner]
            HT[🏨 Agoda, Booking, LiteAPI]
        end
    end

    %% Payment
    subgraph Financials [Checkout & Ticketing]
        MIDTRANS[(💳 Midtrans SNAP API)]
        POSTGRES[(🐘 DB: PostgreSQL)]
        TICKET[E-Ticket Issuer]
    end

    %% Connections
    U_TG --> TG_BOT
    U_OC --> OC_HOOK

    TG_BOT --> GROQ
    TG_BOT --> FALLBACK
    OC_HOOK --> ROUTER

    GROQ --> ROUTER
    FALLBACK --> ROUTER

    ROUTER --> AGGREGATOR
    AGGREGATOR --> TR
    AGGREGATOR --> FL
    AGGREGATOR --> HT
    
    TR --> CHEAPEST
    FL --> CHEAPEST
    HT --> CHEAPEST

    CHEAPEST --> |Checkout| MIDTRANS
    MIDTRANS -.-> |Webhook Paid| OC_HOOK
    
    OC_HOOK --> TICKET
    TICKET --> POSTGRES
    TICKET -.-> |Send PNR PDF/Text| U_TG
```

---

## 🚀 Quick Start (Docker - Recommended)

```bash
# 1. Clone & enter repository
git clone https://github.com/Timcuan/openclaw-travel-agent.git
cd openclaw-travel-agent

# 2. Setup environment variables
cp .env.example .env

# 3. Edit .env with your keys (Groq, Telegram, Midtrans)
nano .env

# 4. Bring up the Database, Redis, Telegram Bot, and FastAPI Server
docker-compose up --build -d
```

> **Untuk Pengguna OpenClaw Framework**: Jalankan `bash scripts/install_skill.sh` untuk mendaftarkan agensi ini sebagai _Skill Native_ di mesin lokal Anda yang bisa dipanggil dari UI/CLI utama OpenClaw.

---

## 🛡️ Live Deployment (Linux VPS/Debian)

To deploy the bot as a highly-available standard background service:

1. **Persiapkan Script Dual-Core Start:**
   ```bash
   chmod +x scripts/start_prod.sh
   ```
2. **Pasang Systemd Daemon:**
   ```bash
   sudo cp deploy/openclaw-travel-agent.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now openclaw-travel-agent
   sudo systemctl status openclaw-travel-agent
   ```
   *Note: Pastikan Anda menyesuaikan path `/opt/openclaw-travel-agent` yang ada di dalam file `.service` dengan lokasi ekstraksi folder Anda.*

---

## 🔑 Environment Variables

Minimum required keys to operate the flow seamlessly:

```ini
GROQ_API_KEY=gsk_...          # Groq AI Token (Dapatkan gratis di console.groq.com)
TELEGRAM_BOT_TOKEN=123:ABC... # Token Bot (Dapatkan dari @BotFather Telegram)

# MIDTRANS LIVE PAYMENT (Dashboard Midtrans -> Settings -> Access Keys)
MIDTRANS_SERVER_KEY=SB-Mid-server-xxxxxxxxxxxxxx
MIDTRANS_IS_PRODUCTION=false  # Ubah ke true jika menggunakan kunci Production asli
```

> **Webhook configuration for Midtrans:** Make sure you set your Midtrans Payment Notification URL to `https://<YOUR-DOMAIN>/payment/webhook` so the bot can verify hashes (SHA-512) and issue tickets securely.

---

## 🧪 Testing

The test suite runs entirely offline by mocking the API dependencies and the Telegram hooks.

```bash
python3.11 -m pytest tests/ -v
# → 28 passed in 0.08s (No keys required)
```

---

## 📜 License
MIT License.
