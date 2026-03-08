"""
Agoda scraper using Playwright (fallback for hotel search).

Agoda does not expose a public API. This uses Playwright to scrape
search results as a last-resort fallback.
"""
import os
from typing import Optional
# playwright imported lazily inside async function (optional dependency)
from utils.logger import logger

HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
TIMEOUT = int(os.getenv("PLAYWRIGHT_TIMEOUT", "30000"))
AGODA_URL = "https://www.agoda.com/search"


async def agoda_search_hotels(
    city: str,
    check_in: str,
    check_out: str,
    adults: int = 2,
    rooms: int = 1
) -> list[dict]:
    """Scrape Agoda for hotel availability."""
    logger.info(f"[Agoda] Scraping hotels in {city} {check_in}→{check_out}")

    results = []
    try:
        from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=HEADLESS)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="id-ID",
            )
            page = await context.new_page()

            url = (
                f"{AGODA_URL}?city={city.replace(' ', '+')}"
                f"&checkIn={check_in}&checkOut={check_out}"
                f"&adults={adults}&rooms={rooms}&textToSearch={city}"
            )
            await page.goto(url, timeout=TIMEOUT)
            await page.wait_for_load_state("networkidle", timeout=TIMEOUT)
            await page.wait_for_timeout(2000)

            hotel_cards = await page.query_selector_all(
                '[data-testid="property-card"], .PropertyCard, [class*="hotel-item"]'
            )
            logger.info(f"[Agoda] Found {len(hotel_cards)} raw cards")

            for card in hotel_cards[:10]:
                try:
                    result = await _parse_agoda_card(card, city, check_in, check_out)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.debug(f"[Agoda] Card parse error: {e}")

            await browser.close()

    except PlaywrightTimeout:
        logger.warning(f"[Agoda] Timeout scraping {city}")
    except Exception as e:
        logger.error(f"[Agoda] Scraper error: {e}")

    if not results:
        results = _mock_agoda_results(city, check_in, check_out)

    logger.info(f"[Agoda] Returning {len(results)} results")
    return results


async def _parse_agoda_card(
    card,
    city: str,
    check_in: str,
    check_out: str
) -> Optional[dict]:
    import re
    text = await card.inner_text()
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    price_match = re.search(r"[\d.,]{5,}", text.replace(" ", ""))
    if not price_match:
        return None

    price_raw = price_match.group().replace(".", "").replace(",", "")
    try:
        price = float(price_raw)
    except ValueError:
        return None

    # Try to get rating
    rating_match = re.search(r"(\d+\.?\d*)\s*/\s*10", text)
    score = float(rating_match.group(1)) if rating_match else 0.0

    # Try to find star count
    star_match = re.search(r"(\d)\s*[Bb]int", text)
    stars = int(star_match.group(1)) if star_match else 3

    return {
        "provider": "Agoda",
        "hotel_name": lines[0] if lines else "Unknown Hotel",
        "city": city,
        "address": "",
        "check_in": check_in,
        "check_out": check_out,
        "star_rating": stars,
        "review_score": score,
        "price_per_night": price,
        "total_price": price,
        "currency": "IDR",
        "room_type": "Standard",
        "breakfast_included": False,
        "cancellation_policy": "See details",
        "image_url": "",
        "source": "agoda_scraper",
    }


def _mock_agoda_results(city: str, check_in: str, check_out: str) -> list[dict]:
    return [
        {
            "provider": "Agoda",
            "hotel_name": f"Novotel {city}",
            "city": city,
            "address": f"Jl. Gatot Subroto No.1, {city}",
            "check_in": check_in,
            "check_out": check_out,
            "star_rating": 4,
            "review_score": 8.4,
            "price_per_night": 550000,
            "total_price": 550000,
            "currency": "IDR",
            "room_type": "Superior Room",
            "breakfast_included": True,
            "cancellation_policy": "Free cancellation",
            "image_url": "",
            "source": "agoda_mock",
        },
        {
            "provider": "Agoda",
            "hotel_name": f"Swiss-Belhotel {city}",
            "city": city,
            "address": f"Jl. Imam Bonjol No.5, {city}",
            "check_in": check_in,
            "check_out": check_out,
            "star_rating": 3,
            "review_score": 7.9,
            "price_per_night": 320000,
            "total_price": 320000,
            "currency": "IDR",
            "room_type": "Standard Room",
            "breakfast_included": False,
            "cancellation_policy": "Non-refundable",
            "image_url": "",
            "source": "agoda_mock",
        },
    ]
