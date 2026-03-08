"""
AI Travel Agent – Groq-powered tool-calling agent.

Workflow:
  1. Receive user message
  2. Build conversation with system prompt + history
  3. Call Groq with tool definitions
  4. If tool_call → execute tool → feed result back → get final response
  5. Return formatted text to bot

Tools: search_train, search_flight, search_hotel, book_ticket, check_booking

File: ai/travel_agent.py
"""
import json
from datetime import datetime
from utils.logger import logger
import services.session_manager as sm
from ai.groq_client import generate_response, extract_tool_call, extract_text

TODAY = datetime.now().strftime("%Y-%m-%d")

SYSTEM_PROMPT = f"""You are OpenClaw, a smart Indonesian travel assistant on Telegram/WhatsApp.

Today's date: {TODAY}

Behavior:
- Respond in the SAME language the user writes in (Indonesian or English).
- Be concise and friendly.
- Always search first, then show results before asking for booking details.
- When the user says a number (1, 2, 3...) after search results, call book_ticket.
- Format prices as "Rp450.000" (Indonesian style).
- For train routes under 800km, prefer train. For longer routes, prefer flight.

Date parsing (Indonesian):
- besok = tomorrow
- lusa = day after tomorrow
- malam ini / hari ini = today
- minggu depan = next week
- akhir pekan / sabtu = coming Saturday

Never make up results. Always call the appropriate search tool first."""


# ─── Main agent entry point ────────────────────────────────────────────────────

async def run_agent(user_id: str, user_text: str) -> str:
    """
    Run one agent turn for a user message.

    Routing logic:
    - Booking flow stages (awaiting_name, awaiting_payment, results_shown + digit)
      → delegated to rule-based agent (exact state machine, no LLM guessing)
    - Everything else → Groq tool-calling agent
    - If Groq key missing → rule-based agent fallback

    Args:
        user_id: Unique user identifier.
        user_text: Incoming message text.

    Returns:
        Agent reply string (Markdown).
    """
    from agent.openclaw_agent import handle_message as _rule_agent
    import services.session_manager as _sm

    # ── Stage guard: booking flow handled by rule-based state machine ────────
    stage = await _sm.get_stage(user_id)
    text_stripped = user_text.strip()

    BOOKING_STAGES = {"awaiting_name", "awaiting_payment", "complete"}
    if stage in BOOKING_STAGES:
        return await _rule_agent(user_id, user_text)

    # results_shown + bare digit → user selected an option
    if stage == "results_shown" and text_stripped.isdigit():
        return await _rule_agent(user_id, user_text)

    # Load conversation history from session
    session = await sm.get_session(user_id)
    history: list[dict] = session.get("history", [])

    # Build messages
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history[-12:])
    messages.append({"role": "user", "content": user_text})

    try:
        # Step 1: Ask Groq to decide intent / tool call
        response = await generate_response(messages, tools=True)
        tool_call = extract_tool_call(response)

        if tool_call:
            tool_name, tool_args = tool_call
            logger.info(f"[TravelAgent] Tool call: {tool_name}({tool_args})")

            # Step 2: Execute tool
            tool_result = await _execute_tool(user_id, tool_name, tool_args)

            # Step 3: Feed tool result back to Groq for final formatting
            assistant_msg = response["choices"][0]["message"]
            messages.append(assistant_msg)
            messages.append({
                "role": "tool",
                "tool_call_id": assistant_msg["tool_calls"][0]["id"],
                "content": json.dumps(tool_result, ensure_ascii=False, default=str),
            })

            final_response = await generate_response(messages, tools=False)
            reply = extract_text(final_response)
        else:
            reply = extract_text(response)

        # Update history (only for search/discovery turns)
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply or ""})
        await sm.update_session(user_id, history=history[-20:])

        return reply or "Maaf, terjadi kesalahan. Coba lagi. 🙏"

    except RuntimeError as e:
        # GROQ_API_KEY missing – fall back to rule-based agent
        if "GROQ_API_KEY" in str(e):
            logger.warning("[TravelAgent] No Groq key – using rule-based agent")
            return await _rule_agent(user_id, user_text)
        logger.error(f"[TravelAgent] Unexpected error: {e}")
        return await _rule_agent(user_id, user_text)
    except Exception as e:
        logger.error(f"[TravelAgent] Error: {e}")
        return await _rule_agent(user_id, user_text)



# ─── Tool executor ─────────────────────────────────────────────────────────────

async def _execute_tool(user_id: str, name: str, args: dict) -> dict:
    """Dispatch tool call to the appropriate service."""
    if name == "search_train":
        return await _tool_search_train(user_id, args)
    if name == "search_flight":
        return await _tool_search_flight(user_id, args)
    if name == "search_hotel":
        return await _tool_search_hotel(user_id, args)
    if name == "book_ticket":
        return await _tool_book_ticket(user_id, args)
    if name == "check_booking":
        return await _tool_check_booking(user_id, args)
    return {"error": f"Unknown tool: {name}"}


async def _tool_search_train(user_id: str, args: dict) -> dict:
    from services.provider_manager import run_search
    from services.cheapest_engine import run as cheapest_run
    from services.deal_detector import tag_deals
    from utils.location_resolver import resolve_train_station

    origin = resolve_train_station(args.get("origin", "")) or args.get("origin", "")
    dest = resolve_train_station(args.get("destination", "")) or args.get("destination", "")
    date = args.get("date", "")
    passengers = args.get("passengers", 1)

    # Check cache first
    import cache.search_cache as sc
    cached = await sc.get_train(origin, dest, date)
    if cached:
        return {"results": cached, "cached": True, "count": len(cached)}

    norm_results = await run_search("train", {"origin": origin, "destination": dest, "date": date, "passengers": passengers})
    raw = [r.to_dict() for r in norm_results]
    ranked = cheapest_run(raw, "train", top_n=5)
    ranked = tag_deals(ranked, "train")

    await sc.set_train(origin, dest, date, ranked)
    await sm.store_results(user_id, "train", ranked)

    return {"results": ranked, "cached": False, "count": len(ranked), "origin": origin, "destination": dest, "date": date}


async def _tool_search_flight(user_id: str, args: dict) -> dict:
    from services.provider_manager import run_search
    from services.cheapest_engine import run as cheapest_run
    from services.deal_detector import tag_deals
    from utils.location_resolver import resolve_airport
    import cache.search_cache as sc

    origin = resolve_airport(args.get("origin", "")) or args.get("origin", "")
    dest = resolve_airport(args.get("destination", "")) or args.get("destination", "")
    date = args.get("date", "")

    cached = await sc.get_flight(origin, dest, date)
    if cached:
        return {"results": cached, "cached": True}

    norm = await run_search("flight", {"origin": origin, "destination": dest, "date": date, "passengers": args.get("passengers", 1)})
    raw = [r.to_dict() for r in norm]
    ranked = cheapest_run(raw, "flight", top_n=5)
    ranked = tag_deals(ranked, "flight")

    await sc.set_flight(origin, dest, date, ranked)
    await sm.store_results(user_id, "flight", ranked)
    return {"results": ranked, "count": len(ranked), "origin": origin, "destination": dest}


async def _tool_search_hotel(user_id: str, args: dict) -> dict:
    from services.provider_manager import run_search
    from services.cheapest_engine import run as cheapest_run
    from services.deal_detector import tag_deals
    from utils.location_resolver import resolve_hotel_city
    import cache.search_cache as sc

    city = resolve_hotel_city(args.get("city", ""))
    check_in = args.get("check_in", "")
    check_out = args.get("check_out", "")

    cached = await sc.get_hotel(city, check_in, check_out)
    if cached:
        return {"results": cached, "cached": True}

    norm = await run_search("hotel", {"city": city, "check_in": check_in, "check_out": check_out, "adults": args.get("adults", 2), "rooms": args.get("rooms", 1)})
    raw = [r.to_dict() for r in norm]
    ranked = cheapest_run(raw, "hotel", top_n=5)
    ranked = tag_deals(ranked, "hotel")

    await sc.set_hotel(city, check_in, check_out, ranked)
    await sm.store_results(user_id, "hotel", ranked)
    return {"results": ranked, "count": len(ranked), "city": city}


async def _tool_book_ticket(user_id: str, args: dict) -> dict:
    option_n = args.get("option_number", 1)
    offer = await sm.get_selected_offer(user_id, option_n)
    if not offer:
        _, results = await sm.get_results(user_id)
        return {"error": f"Option {option_n} not found. Available: 1-{len(results)}"}

    await sm.update_session(user_id, stage="awaiting_name", selected_option=option_n, selected_offer=offer)
    travel_type = (await sm.get_session(user_id)).get("travel_type", "")
    price = offer.get("price", 0)

    return {
        "selected": True,
        "offer": offer,
        "travel_type": travel_type,
        "price_idr": price,
        "next_step": "Ask user for full passenger name to proceed with booking.",
    }


async def _tool_check_booking(user_id: str, args: dict) -> dict:
    from services.booking_manager import get_booking
    booking_id = args.get("booking_id", "")
    order = await get_booking(booking_id)
    if not order:
        return {"found": False, "message": f"Booking {booking_id} not found."}
    return {"found": True, "booking": order}
