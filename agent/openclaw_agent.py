"""
OpenClaw Agent v3 – AI Travel Concierge.

New in v3:
  - Travel Planning Mode: "trip ke bandung weekend ini" → train + hotel combo
  - Transport Decider: auto train/flight recommendation by distance
  - Multi-Search Engine + Result Ranker (multi-factor scoring)
  - Deal Detector: 🔥 BEST DEAL / ✅ GOOD PRICE tags on results
  - Price Alert commands: "pantau tiket surabaya jakarta"
  - Booking Manager: persistent orders with UUID booking IDs
  - Booking history: /pesanan command
  - Smart NLP + date parser integration

Booking state machine (Redis session):
  idle → results_shown → awaiting_name → awaiting_payment → complete

File: agent/openclaw_agent.py
"""
import asyncio
from utils.logger import logger

# Services
import services.session_manager as sm
import cache.search_cache as sc
from services.multi_search_engine import search as multi_search
from services.result_ranker import rank
from services.deal_detector import tag_deals
from services.booking_manager import create_booking, list_user_bookings, format_order_confirmation
from services.price_alerts import add_alert

# Agent
from agent.nlp_parser import parse_intent, ParsedIntent
from agent.transport_decider import decide as transport_decide, format_decision

# Formatters
from services.cheapest_engine import format_results as ce_format_results, format_price

# ─── Constants ────────────────────────────────────────────────────────────────

WELCOME = (
    "👋 Selamat datang di *OpenClaw Travel Concierge*! 🌏\n\n"
    "Saya mencari harga *terbaik & termurah* dari semua provider secara otomatis.\n\n"
    "✨ *Coba perintah ini:*\n"
    "🚂 `kereta surabaya jakarta besok`\n"
    "✈️ `pesawat bali jakarta besok pagi`\n"
    "🏨 `hotel murah bandung 2 malam`\n"
    "🗺️ `trip ke bandung akhir pekan ini`\n"
    "🔔 `pantau tiket surabaya jakarta`\n"
    "📋 `/pesanan` — lihat pesanan kamu\n\n"
    "_Ketik pencarian Anda sekarang!_"
)

PAYMENT_OPTIONS = (
    "💳 *Pilih metode pembayaran:*\n\n"
    "1️⃣  Transfer Bank (BCA / Mandiri / BNI)\n"
    "2️⃣  GoPay / OVO / DANA\n"
    "3️⃣  Kartu Kredit / Debit\n"
    "4️⃣  Minimarket (Indomaret / Alfamart)\n\n"
    "_Balas nomor pilihan. Contoh:_ *2*"
)

PAYMENT_NAMES = {
    "1": "Transfer Bank",
    "2": "GoPay / OVO / DANA",
    "3": "Kartu Kredit",
    "4": "Minimarket",
}

ALERT_KEYWORDS = ["pantau", "alert", "notif", "beritahu", "watch", "monitor"]
TRIP_KEYWORDS = ["trip", "liburan", "wisata", "perjalanan ke", "mau ke", "jalan-jalan ke"]
HISTORY_COMMANDS = ["/pesanan", "/history", "pesanan saya", "lihat pesanan"]


# ─── Main entry point ─────────────────────────────────────────────────────────

async def handle_message(user_id: str, text: str) -> str:
    text = text.strip()
    low = text.lower()
    stage = await sm.get_stage(user_id)

    # ── Global commands ──────────────────────────────────────────────────────
    if low in ("/start", "halo", "hai", "hello", "hi", "mulai", "start"):
        await sm.reset_session(user_id)
        return WELCOME

    if low in ("/reset", "reset", "batal", "cancel", "ulang"):
        await sm.reset_session(user_id)
        return "🔄 Sesi direset. Mulai pencarian baru.\n\n" + WELCOME

    if low in ("/help", "help", "bantuan", "?"):
        return WELCOME

    if any(low.startswith(cmd) for cmd in HISTORY_COMMANDS):
        return await _show_history(user_id)

    # ── Booking flow ─────────────────────────────────────────────────────────
    if stage == "awaiting_payment":
        return await _handle_payment(user_id, text)

    if stage == "awaiting_name":
        return await _handle_name(user_id, text)

    if stage == "results_shown" and text.strip().isdigit():
        return await _handle_selection(user_id, int(text.strip()))

    # ── Price alert command ──────────────────────────────────────────────────
    if any(kw in low for kw in ALERT_KEYWORDS):
        return await _handle_alert_request(user_id, text)

    # ── Travel planning mode ─────────────────────────────────────────────────
    if any(kw in low for kw in TRIP_KEYWORDS):
        return await _handle_trip_planning(user_id, text)

    # ── Main search ──────────────────────────────────────────────────────────
    return await _handle_search(user_id, text)


# ─── Search flow ──────────────────────────────────────────────────────────────

async def _handle_search(user_id: str, text: str) -> str:
    intent: ParsedIntent = await parse_intent(text)

    if intent.intent == "unknown":
        return f"🤔 {intent.message or 'Tidak dimengerti.'}"

    if intent.intent == "booking" and intent.option_number:
        return "⚠️ Silakan lakukan pencarian dulu.\nContoh: `kereta surabaya jakarta besok`"

    travel_type = {
        "search_train": "train",
        "search_flight": "flight",
        "search_hotel": "hotel",
    }.get(intent.intent)

    if not travel_type:
        return "🤔 Tidak dimengerti. Coba: `kereta surabaya jakarta besok`"

    err = _validate_intent(intent, travel_type)
    if err:
        return err

    # Transport auto-decide for ambiguous queries
    transport_hint = ""
    if travel_type == "train" and intent.origin and intent.destination:
        decision = transport_decide(intent.origin, intent.destination)
        if decision.show_both:
            transport_hint = f"\n💡 _{format_decision(decision)}_\n"

    # Cache check
    cached = await _cache_get(intent, travel_type)
    if cached is not None:
        await sm.store_results(user_id, travel_type, cached)
        return _format_with_deals(travel_type, cached) + "\n\n⚡ _(dari cache)_"

    # Live search
    search_result = await multi_search(
        travel_type,
        origin=intent.origin or "",
        destination=intent.destination or "",
        date=intent.date or "",
        city=intent.city or "",
        check_in=intent.check_in or "",
        check_out=intent.check_out or "",
        passengers=intent.passengers,
        rooms=intent.rooms,
    )

    raw = search_result["results"]
    if not raw:
        return (
            "😔 *Tidak ditemukan hasil* untuk pencarian ini.\n"
            "Coba rute atau tanggal berbeda."
        )

    # Rank + tag deals
    results = rank(raw, travel_type, top_n=5)
    results = tag_deals(results, travel_type)

    # Cache + store in session
    await _cache_set(intent, travel_type, results)
    await sm.store_results(user_id, travel_type, results)

    providers_ok = ", ".join(search_result.get("providers_called", []))
    footer = f"\n\n_Dicari dari: {providers_ok} dalam {search_result.get('duration_ms',0)}ms_"

    return transport_hint + _format_with_deals(travel_type, results) + footer


# ─── Travel planning mode ─────────────────────────────────────────────────────

async def _handle_trip_planning(user_id: str, text: str) -> str:
    """
    Handle "trip ke bandung weekend ini" style requests.
    Returns combined transport + hotel suggestions.
    """
    intent: ParsedIntent = await parse_intent(text)
    city = intent.city or intent.destination or intent.origin or ""
    date = intent.date or intent.check_in or ""

    if not city:
        return "🤔 Kota tujuan tidak ditemukan. Coba: `trip ke bandung akhir pekan ini`"

    logger.info(f"[Concierge] Trip planning to {city} on {date}")

    # Run train + hotel search in parallel
    from datetime import datetime, timedelta
    try:
        check_in = date
        check_out_dt = datetime.strptime(date, "%Y-%m-%d") + timedelta(days=2)
        check_out = check_out_dt.strftime("%Y-%m-%d")
    except ValueError:
        check_out = date

    train_task = multi_search(
        "train",
        origin=intent.origin or "Jakarta",
        destination=city,
        date=date,
        passengers=intent.passengers,
    )
    hotel_task = multi_search(
        "hotel",
        city=city,
        check_in=check_in,
        check_out=check_out,
        passengers=intent.passengers,
    )

    train_result, hotel_result = await asyncio.gather(train_task, hotel_task)

    # Rank results
    trains = rank(train_result["results"], "train", top_n=3)
    trains = tag_deals(trains, "train")
    hotels = rank(hotel_result["results"], "hotel", top_n=3)
    hotels = tag_deals(hotels, "hotel")

    # Build combined reply
    lines = [f"🗺️ *Trip ke {city.capitalize()}*  📅 {date}\n"]

    if trains:
        lines.append("🚂 *Pilihan Kereta:*")
        for r in trains:
            deal = f" {r.get('deal_tag','')}" if r.get("deal_tag") else ""
            lines.append(
                f"  *{r['rank']}.* {r.get('train_name','?')}  {r.get('departure_time','--')}"
                f"\n       💰 *{format_price(r['price'])}*{deal}"
            )
        lines.append("")

    if hotels:
        lines.append("🏨 *Pilihan Hotel:*")
        for r in hotels:
            deal = f" {r.get('deal_tag','')}" if r.get("deal_tag") else ""
            lines.append(
                f"  *{r['rank']}.* {r.get('hotel_name','?')}"
                f"\n       💰 *{format_price(r['price'])}/malam*{deal}"
            )
        lines.append("")

    lines.append("_Ketik 'kereta' atau 'hotel' untuk pencarian detail & booking._")
    return "\n".join(lines)


# ─── Price alert handler ──────────────────────────────────────────────────────

async def _handle_alert_request(user_id: str, text: str) -> str:
    intent: ParsedIntent = await parse_intent(text)
    travel_type = {
        "search_train": "train",
        "search_flight": "flight",
        "search_hotel": "hotel",
    }.get(intent.intent, "train")

    origin = intent.origin or ""
    destination = intent.destination or intent.city or ""
    date = intent.date or intent.check_in or ""

    if not (origin or destination):
        return "⚠️ Tidak bisa membuat alert – sebutkan rute.\nContoh: `pantau tiket surabaya jakarta`"

    # Get current best price as baseline
    search_result = await multi_search(
        travel_type,
        origin=origin,
        destination=destination,
        date=date,
        city=intent.city or "",
        check_in=intent.check_in or date,
        check_out=intent.check_out or date,
    )
    results = rank(search_result["results"], travel_type, top_n=1)
    baseline = results[0]["price"] if results else 0

    await add_alert(
        user_id=user_id,
        travel_type=travel_type,
        origin=origin,
        destination=destination,
        date=date,
        current_best_price=baseline,
        city=intent.city or "",
    )

    emoji = {"train": "🚂", "flight": "✈️", "hotel": "🏨"}.get(travel_type, "🎫")
    route = f"{origin} → {destination}" if destination else destination
    baseline_str = f" (harga sekarang *{format_price(baseline)}*)" if baseline else ""

    return (
        f"🔔 *Alert aktif!* {emoji}\n\n"
        f"Rute: *{route}*  📅 {date}\n"
        f"{baseline_str}\n\n"
        "Kami akan memberi tahu jika ada harga *lebih murah* dalam 7 hari ke depan. 👍"
    )


# ─── Booking flow stages ──────────────────────────────────────────────────────

async def _handle_selection(user_id: str, option_n: int) -> str:
    offer = await sm.get_selected_offer(user_id, option_n)
    if not offer:
        _, results = await sm.get_results(user_id)
        return f"⚠️ Pilihan *{option_n}* tidak valid. Ketik 1–{len(results)}."

    await sm.update_session(user_id, stage="awaiting_name",
                             selected_option=option_n, selected_offer=offer)
    travel_type = (await sm.get_session(user_id)).get("travel_type", "")
    return (
        f"✅ *Anda memilih:*\n{_offer_summary(travel_type, offer)}\n\n"
        "👤 Masukkan *nama lengkap* penumpang:"
    )


async def _handle_name(user_id: str, name: str) -> str:
    name = name.strip()
    if len(name) < 3:
        return "⚠️ Nama terlalu pendek. Masukkan nama lengkap:"
    await sm.update_session(user_id, stage="awaiting_payment", passenger_name=name)
    return f"✅ Nama: *{name}*\n\n" + PAYMENT_OPTIONS


async def _handle_payment(user_id: str, choice: str) -> str:
    payment_name = PAYMENT_NAMES.get(choice.strip())
    if not payment_name:
        return "⚠️ Pilih 1–4:\n\n" + PAYMENT_OPTIONS

    session = await sm.get_session(user_id)
    offer = session.get("selected_offer", {})
    name = session.get("passenger_name", "")
    travel_type = session.get("travel_type", "")

    # Create persistent booking
    order = await create_booking(
        user_id=user_id,
        travel_type=travel_type,
        offer=offer,
        passenger_name=name,
        payment_method=payment_name,
    )
    await sm.update_session(user_id, stage="complete", payment_method=payment_name)

    return format_order_confirmation(order)


# ─── History ───────────────────────────────────────────────────────────────────

async def _show_history(user_id: str) -> str:
    bookings = await list_user_bookings(user_id, limit=5)
    if not bookings:
        return "📋 Belum ada pesanan.\n\nMulai dengan pencarian tiket! 🔍"
    lines = ["📋 *Pesanan Kamu:*\n"]
    for b in bookings:
        status = "⏳ Menunggu" if b.get("status") == "pending_payment" else "✅ Konfirmasi"
        price = format_price(b.get("price", 0))
        lines.append(
            f"`{b.get('booking_id','?')}` – {b.get('travel_type','?').upper()}\n"
            f"   {status}  |  💰 {price}\n"
        )
    return "\n".join(lines)


# ─── Utilities ────────────────────────────────────────────────────────────────

def _format_with_deals(travel_type: str, results: list[dict]) -> str:
    """Format results using cheapest_engine formatter with deal tags injected."""
    formatted = ce_format_results(travel_type, results)
    # Inject deal tags into formatted text
    for r in results:
        tag = r.get("deal_tag", "")
        name = r.get("train_name") or r.get("flight_number") or r.get("hotel_name") or ""
        if tag and name:
            formatted = formatted.replace(f"{name}", f"{name}  {tag}", 1)
    return formatted


async def _cache_get(intent: ParsedIntent, travel_type: str):
    if travel_type == "train":
        return await sc.get_train(intent.origin or "", intent.destination or "", intent.date or "")
    if travel_type == "flight":
        return await sc.get_flight(intent.origin or "", intent.destination or "", intent.date or "")
    if travel_type == "hotel":
        return await sc.get_hotel(intent.city or "", intent.check_in or "", intent.check_out or "")
    return None


async def _cache_set(intent: ParsedIntent, travel_type: str, results: list):
    if travel_type == "train":
        await sc.set_train(intent.origin or "", intent.destination or "", intent.date or "", results)
    elif travel_type == "flight":
        await sc.set_flight(intent.origin or "", intent.destination or "", intent.date or "", results)
    elif travel_type == "hotel":
        await sc.set_hotel(intent.city or "", intent.check_in or "", intent.check_out or "", results)


def _validate_intent(intent: ParsedIntent, travel_type: str) -> str | None:
    if travel_type in ("train", "flight"):
        if not intent.origin:
            return "⚠️ Kota asal tidak dikenali.\nContoh: `kereta *Surabaya* Jakarta besok`"
        if not intent.destination:
            return "⚠️ Kota tujuan tidak dikenali.\nContoh: `kereta Surabaya *Jakarta* besok`"
    if travel_type == "hotel" and not intent.city:
        return "⚠️ Kota hotel tidak dikenali.\nContoh: `hotel *Bandung* 2 malam`"
    return None


def _offer_summary(travel_type: str, offer: dict) -> str:
    price = offer.get("price", 0) or offer.get("price_per_night", 0)
    p = format_price(price)
    if travel_type == "train":
        return (
            f"🚂 *{offer.get('train_name','?')}*  "
            f"{offer.get('departure_time','--')} → {offer.get('arrival_time','--')}\n"
            f"   💰 {p}"
        )
    if travel_type == "flight":
        return (
            f"✈️ *{offer.get('airline','?')} {offer.get('flight_number','')}*\n"
            f"   💰 {p}"
        )
    if travel_type == "hotel":
        return (
            f"🏨 *{offer.get('hotel_name','?')}*\n"
            f"   {offer.get('check_in','')} → {offer.get('check_out','')}\n"
            f"   💰 {p}/malam"
        )
    return p
