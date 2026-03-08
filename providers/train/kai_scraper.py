"""
KAI (PT Kereta Api Indonesia) scraper using Playwright.

Scrapes https://booking.kai.id for train availability.
This is the fallback / primary scraper when no official API is available.
"""
import asyncio
import os
from datetime import datetime
from typing import Optional

# playwright imported lazily inside async function (optional dependency)
from utils.logger import logger
from utils.city_mapper import city_to_station, station_to_city

KAI_URL = os.getenv("KAI_BASE_URL", "https://booking.kai.id")
HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
TIMEOUT = int(os.getenv("PLAYWRIGHT_TIMEOUT", "30000"))


async def kai_search_trains(
    origin: str,
    destination: str,
    date: str,
    adult: int = 1
) -> list[dict]:
    """
    Scrape KAI booking site for available trains.

    Args:
        origin: Station code or city name (e.g. "SBI" or "Surabaya")
        destination: Station code or city name (e.g. "GMR" or "Jakarta")
        date: Date in YYYY-MM-DD format
        adult: Number of adult passengers

    Returns:
        List of train result dicts with normalised schema.
    """
    origin_code = city_to_station(origin) or origin.upper()
    dest_code = city_to_station(destination) or destination.upper()

    logger.info(f"[KAI] Searching {origin_code}→{dest_code} on {date}")
    results = []
    # Default fallback in case playwright is not installed
    _PlaywrightTimeout = Exception

    try:
        from playwright.async_api import async_playwright
        from playwright.async_api import TimeoutError as PlaywrightTimeout
        _PlaywrightTimeout = PlaywrightTimeout
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=HEADLESS)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()

            # Navigate and fill form
            await page.goto(KAI_URL, timeout=TIMEOUT)
            await page.wait_for_load_state("networkidle", timeout=TIMEOUT)

            # Try filling origin
            try:
                await page.fill('input[placeholder*="Asal"]', origin_code, timeout=5000)
                await page.wait_for_timeout(800)
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")
            except Exception:
                logger.debug("[KAI] Origin field not found via placeholder, trying other selectors")

            # Try filling destination
            try:
                await page.fill('input[placeholder*="Tujuan"]', dest_code, timeout=5000)
                await page.wait_for_timeout(800)
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")
            except Exception:
                logger.debug("[KAI] Destination field not found")

            # Date
            try:
                fmt_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d/%m/%Y")
                await page.fill('input[type="date"]', date, timeout=5000)
            except Exception:
                logger.debug("[KAI] Date field not found")

            # Search button
            try:
                await page.click('button[type="submit"]', timeout=5000)
                await page.wait_for_load_state("networkidle", timeout=TIMEOUT)
                await page.wait_for_timeout(2000)
            except Exception:
                logger.debug("[KAI] Submit button not found")

            # Parse results
            result_cards = await page.query_selector_all(".train-result, .result-item, [data-train]")
            logger.info(f"[KAI] Found {len(result_cards)} raw result cards")

            for card in result_cards:
                try:
                    text = await card.inner_text()
                    result = _parse_kai_card(text, origin_code, dest_code, date)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.debug(f"[KAI] Error parsing card: {e}")

            await browser.close()

    except _PlaywrightTimeout:
        logger.warning(f"[KAI] Timeout searching {origin_code}→{dest_code}")
    except Exception as e:
        logger.error(f"[KAI] Scraper error: {e}")

    # If scraper got no real results, return mock data for demo
    if not results:
        results = _mock_kai_results(origin_code, dest_code, date)

    logger.info(f"[KAI] Returning {len(results)} results")
    return results


def _parse_kai_card(text: str, origin: str, dest: str, date: str) -> Optional[dict]:
    """Attempt to parse text from a KAI result card."""
    import re
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) < 3:
        return None

    price_match = re.search(r"[\d.,]{5,}", text.replace(" ", ""))
    if not price_match:
        return None

    price_raw = price_match.group().replace(".", "").replace(",", "")
    try:
        price = float(price_raw)
    except ValueError:
        return None

    return {
        "provider": "KAI",
        "train_name": lines[0] if lines else "Unknown",
        "origin": origin,
        "destination": dest,
        "date": date,
        "departure_time": lines[1] if len(lines) > 1 else "--:--",
        "arrival_time": lines[2] if len(lines) > 2 else "--:--",
        "duration": None,
        "seat_class": "Ekonomi",
        "price": price,
        "currency": "IDR",
        "available_seats": None,
        "source": "kai_scraper",
    }


def _mock_kai_results(origin: str, dest: str, date: str) -> list[dict]:
    """Return mock results for demo/fallback when scraper fails."""
    origin_city = station_to_city(origin) or origin
    dest_city = station_to_city(dest) or dest
    return [
        {
            "provider": "KAI",
            "train_name": "Argo Bromo Anggrek",
            "origin": origin,
            "destination": dest,
            "date": date,
            "departure_time": "08:20",
            "arrival_time": "16:50",
            "duration": "8j 30m",
            "seat_class": "Eksekutif",
            "price": 450000,
            "currency": "IDR",
            "available_seats": 20,
            "source": "kai_scraper_mock",
        },
        {
            "provider": "KAI",
            "train_name": "Gajayana",
            "origin": origin,
            "destination": dest,
            "date": date,
            "departure_time": "10:15",
            "arrival_time": "19:45",
            "duration": "9j 30m",
            "seat_class": "Eksekutif",
            "price": 485000,
            "currency": "IDR",
            "available_seats": 15,
            "source": "kai_scraper_mock",
        },
        {
            "provider": "KAI",
            "train_name": "Sembrani",
            "origin": origin,
            "destination": dest,
            "date": date,
            "departure_time": "19:10",
            "arrival_time": "04:00+1",
            "duration": "8j 50m",
            "seat_class": "Bisnis",
            "price": 320000,
            "currency": "IDR",
            "available_seats": 30,
            "source": "kai_scraper_mock",
        },
    ]
