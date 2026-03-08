"""
Groq API client – drop-in LLM backend for OpenClaw Travel Agent.

Model: llama-3.3-70b-versatile
Supports: chat completions, tool calling (function calling)

File: ai/groq_client.py
"""
import os
import json
from typing import Any, Optional
import httpx
from utils.logger import logger

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TIMEOUT = 30

# ─── Tool definitions (OpenAI format) ─────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_train",
            "description": "Search for train tickets between Indonesian cities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin":      {"type": "string", "description": "Origin city or station code"},
                    "destination": {"type": "string", "description": "Destination city or station code"},
                    "date":        {"type": "string", "description": "Travel date YYYY-MM-DD"},
                    "passengers":  {"type": "integer", "description": "Number of passengers", "default": 1},
                },
                "required": ["origin", "destination", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_flight",
            "description": "Search for domestic flights in Indonesia.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin":      {"type": "string", "description": "Origin IATA code or city"},
                    "destination": {"type": "string", "description": "Destination IATA code or city"},
                    "date":        {"type": "string", "description": "Travel date YYYY-MM-DD"},
                    "passengers":  {"type": "integer", "description": "Number of passengers", "default": 1},
                },
                "required": ["origin", "destination", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_hotel",
            "description": "Search for hotels in an Indonesian city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city":      {"type": "string", "description": "City name"},
                    "check_in":  {"type": "string", "description": "Check-in date YYYY-MM-DD"},
                    "check_out": {"type": "string", "description": "Check-out date YYYY-MM-DD"},
                    "adults":    {"type": "integer", "description": "Number of adults", "default": 2},
                    "rooms":     {"type": "integer", "description": "Number of rooms", "default": 1},
                },
                "required": ["city", "check_in", "check_out"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_ticket",
            "description": "Initiate booking for a selected travel option.",
            "parameters": {
                "type": "object",
                "properties": {
                    "option_number": {"type": "integer", "description": "The numbered option the user selected (1-5)"},
                },
                "required": ["option_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_booking",
            "description": "Check existing booking status by booking ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {"type": "string", "description": "The booking order ID (e.g. OCL-XXXXXXXX)"},
                },
                "required": ["booking_id"],
            },
        },
    },
]


# ─── Core API call ─────────────────────────────────────────────────────────────

async def generate_response(
    messages: list[dict],
    tools: bool = True,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> dict:
    """
    Call Groq chat completions API.

    Args:
        messages: OpenAI-format message list.
        tools: Whether to include tool definitions.
        temperature: LLM temperature.
        max_tokens: Max tokens in response.

    Returns:
        Full Groq API response dict.

    Raises:
        RuntimeError if API key is missing or call fails.
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set. Add it to .env file.")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if tools:
        payload["tools"] = TOOL_DEFINITIONS
        payload["tool_choice"] = "auto"

    try:
        async with httpx.AsyncClient(timeout=GROQ_TIMEOUT) as client:
            resp = await client.post(
                f"{GROQ_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.debug(f"[Groq] tokens={data.get('usage',{})}")
            return data
    except httpx.HTTPStatusError as e:
        logger.error(f"[Groq] HTTP {e.response.status_code}: {e.response.text[:300]}")
        raise RuntimeError(f"Groq API error: {e.response.status_code}")
    except Exception as e:
        logger.error(f"[Groq] Client error: {e}")
        raise


def extract_tool_call(response: dict) -> Optional[tuple[str, dict]]:
    """
    Extract tool name and arguments from a Groq response.

    Returns:
        (tool_name, args_dict) or None if no tool call.
    """
    try:
        choice = response["choices"][0]
        tool_calls = choice.get("message", {}).get("tool_calls")
        if tool_calls:
            tc = tool_calls[0]
            name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"])
            return name, args
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.debug(f"[Groq] No tool call extracted: {e}")
    return None


def extract_text(response: dict) -> str:
    """Extract plain text content from a Groq response."""
    try:
        return response["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError):
        return ""
