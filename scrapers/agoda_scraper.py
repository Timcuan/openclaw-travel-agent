"""
Agoda scraper fallback – Playwright-based hotel search.

File: scrapers/agoda_scraper.py
"""
from utils.logger import logger


async def scrape_agoda_hotels(city: str, check_in: str, check_out: str, adults: int = 2, rooms: int = 1) -> list[dict]:
    """Scrape Agoda hotel results. Falls back to mock on failure."""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await (await browser.new_context(user_agent="Mozilla/5.0")).new_page()
            url = (f"https://www.agoda.com/search?city={city.lower()}"
                   f"&checkIn={check_in}&checkOut={check_out}&adults={adults}&rooms={rooms}")
            await page.goto(url, timeout=20000)
            await page.wait_for_timeout(5000)

            results = await page.evaluate("""
                () => {
                    const cards = document.querySelectorAll('[data-selenium="hotel-item"], [class*="hotel-card"]');
                    return Array.from(cards).slice(0, 5).map(c => ({
                        name: c.querySelector('[class*="hotel-name"], h3')?.innerText || '',
                        price: c.querySelector('[class*="price-display"], [class*="discounted"]')?.innerText || '0',
                        stars: c.querySelectorAll('[class*="star"]').length,
                        score: c.querySelector('[class*="review-score"]')?.innerText || '0',
                    }));
                }
            """)
            await browser.close()

            parsed = []
            for r in results:
                price_raw = r.get("price", "0").replace("Rp", "").replace(".", "").replace(",", "").strip()
                try:
                    price = float(price_raw)
                except ValueError:
                    price = 0
                if price > 0:
                    parsed.append({
                        "provider": "Agoda", "hotel_name": r.get("name", "Unknown"),
                        "city": city, "check_in": check_in, "check_out": check_out,
                        "price_per_night": price, "currency": "IDR",
                        "star_rating": r.get("stars", 0),
                        "review_score": float(r.get("score", 0) or 0),
                    })
            return parsed if parsed else _mock(city, check_in, check_out)
    except Exception as e:
        logger.warning(f"[AgodaScraper] {e}")
        return _mock(city, check_in, check_out)


def _mock(city, check_in, check_out):
    return [
        {"provider": "Agoda", "hotel_name": f"Hotel Murah {city}", "city": city,
         "check_in": check_in, "check_out": check_out,
         "price_per_night": 210000, "currency": "IDR", "star_rating": 2, "review_score": 7.2},
        {"provider": "Agoda", "hotel_name": f"{city} Grand Hotel", "city": city,
         "check_in": check_in, "check_out": check_out,
         "price_per_night": 450000, "currency": "IDR", "star_rating": 4, "review_score": 8.7},
    ]
