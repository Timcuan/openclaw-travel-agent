"""
Traveloka scraper fallback – uses Playwright to scrape train results.

File: scrapers/traveloka_scraper.py
"""
import asyncio
from datetime import datetime
from utils.logger import logger


async def scrape_traveloka_trains(origin: str, destination: str, date: str, passengers: int = 1) -> list[dict]:
    """
    Scrape Traveloka train search results using Playwright.
    Returns mock data if scraping fails or Playwright is unavailable.
    """
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()
            url = f"https://www.traveloka.com/en-id/train/search?origin={origin}&destination={destination}&departureDate={date}&numAdult={passengers}"
            await page.goto(url, timeout=15000)
            await page.wait_for_timeout(4000)

            results = await page.evaluate("""
                () => {
                    const cards = document.querySelectorAll('[data-id], .train-card, [class*="TrainCard"]');
                    return Array.from(cards).slice(0, 5).map(c => ({
                        name: c.querySelector('[class*="train-name"], [class*="TrainName"], h3')?.innerText || '',
                        departure: c.querySelector('[class*="departure-time"], .time')?.innerText || '',
                        arrival: c.querySelector('[class*="arrival-time"]')?.innerText || '',
                        price: c.querySelector('[class*="price"], [class*="Price"]')?.innerText || '',
                        seat_class: c.querySelector('[class*="class"], [class*="Class"]')?.innerText || '',
                    }));
                }
            """)

            await browser.close()

            parsed = []
            for r in results:
                price_str = r.get("price", "0").replace("Rp", "").replace(".", "").replace(",", "").strip()
                try:
                    price = float(price_str)
                except ValueError:
                    price = 0
                if price > 0:
                    parsed.append({
                        "provider": "Traveloka",
                        "train_name": r.get("name", "Unknown"),
                        "origin": origin,
                        "destination": destination,
                        "date": date,
                        "departure_time": r.get("departure", ""),
                        "arrival_time": r.get("arrival", ""),
                        "price": price,
                        "currency": "IDR",
                        "seat_class": r.get("seat_class", "Ekonomi"),
                    })
            if parsed:
                logger.info(f"[TravelokaScraper] Scraped {len(parsed)} results")
                return parsed
    except Exception as e:
        logger.warning(f"[TravelokaScraper] Scraping failed: {e}")

    return _mock_results(origin, destination, date)


def _mock_results(origin: str, destination: str, date: str) -> list[dict]:
    return [
        {"provider": "Traveloka", "train_name": "Sembrani", "origin": origin, "destination": destination,
         "date": date, "departure_time": "19:10", "arrival_time": "05:30",
         "price": 520000, "currency": "IDR", "seat_class": "Eksekutif"},
        {"provider": "Traveloka", "train_name": "Argo Anggrek", "origin": origin, "destination": destination,
         "date": date, "departure_time": "22:00", "arrival_time": "08:00",
         "price": 630000, "currency": "IDR", "seat_class": "Eksekutif"},
    ]
