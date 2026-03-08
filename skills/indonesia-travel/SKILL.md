---
name: indonesia-travel
description: >
  Search and book Indonesia domestic travel: trains (kereta api via KAI),
  flights (pesawat), and hotels. Use this skill when the user wants to search
  for the cheapest train ticket, flight, or hotel in Indonesia. Also use it
  when the user mentions cities like Surabaya, Jakarta, Bandung, Bali, Medan,
  Yogyakarta, etc. in a travel context. Supports natural language in Indonesian
  and English. Keywords that trigger this skill: kereta, pesawat, hotel, tiket,
  travel, perjalanan, murah, train, flight, book, pesan, cari jadwal.
homepage: http://localhost:8000/docs
user-invocable: true
env:
  OPENCLAW_TRAVEL_API: "http://localhost:8000"
---

# Indonesia Travel Skill

You are connected to the **OpenClaw Travel Agent** – a smart Indonesia domestic travel assistant.

## Base URL
`{env.OPENCLAW_TRAVEL_API}` (default: `http://localhost:8000`)

## Available Tools

### 1. Search Trains
```
POST {env.OPENCLAW_TRAVEL_API}/openclaw/search
Content-Type: application/json

{
  "query": "<natural language Indonesian query>",
  "type": "train"
}
```

### 2. Search Flights
```
POST {env.OPENCLAW_TRAVEL_API}/openclaw/search
Content-Type: application/json

{
  "query": "<natural language query>",
  "type": "flight"
}
```

### 3. Search Hotels
```
POST {env.OPENCLAW_TRAVEL_API}/openclaw/search
Content-Type: application/json

{
  "query": "<natural language query>",
  "type": "hotel"
}
```

### 4. Auto-detect (recommended)
```
POST {env.OPENCLAW_TRAVEL_API}/openclaw/search
Content-Type: application/json

{
  "query": "<any travel query in Indonesian or English>"
}
```
The system auto-detects the travel type (train / flight / hotel).

### 5. Check system status
```
GET {env.OPENCLAW_TRAVEL_API}/openclaw/status
```

## Response Format

```json
{
  "travel_type": "train",
  "count": 3,
  "results": [
    {
      "rank": 1,
      "train_name": "Argo Bromo Anggrek",
      "origin": "GMR",
      "destination": "SBI",
      "departure_time": "08:20",
      "arrival_time": "16:50",
      "price": 450000,
      "currency": "IDR",
      "provider": "KAI",
      "deal_tag": "🔥 BEST DEAL"
    }
  ],
  "message": "🚂 Kereta Jakarta → Surabaya | 2026-03-09 ..."
}
```

## Instructions

1. Always call the search endpoint first.
2. Present the `message` field directly to the user – it's already formatted.
3. If the user selects an option (e.g. "1", "pilih 1"), call:
   ```
   POST {env.OPENCLAW_TRAVEL_API}/openclaw/book
   {"user_id": "<user-id>", "option": 1}
   ```
4. Prices are in IDR (Indonesian Rupiah). Format as `Rp 450.000`.
5. Date interpretation (Indonesian):
   - `besok` = tomorrow
   - `lusa` = day after tomorrow
   - `akhir pekan` = coming Saturday
   - `minggu depan` = next Monday

## Notes
- The API runs locally. If it's unavailable, tell the user to start the bot:
  `docker-compose up -d` or `bash scripts/keep-alive.sh`
- The system searches multiple providers in parallel and returns the cheapest results.
- Results are cached for 10 minutes per route.
