"""
Tiket.com scraper fallback – Playwright-based scraping of train results.

File: scrapers/tiket_scraper.py
"""
from utils.logger import logger


async def scrape_tiket_trains(origin: str, destination: str, date: str, passengers: int = 1) -> list[dict]:
    """Scrape Tiket.com train results. Falls back to mock on failure."""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await (await browser.new_context()).new_page()
            date_fmt = date.replace("-", "%2F")
            url = (f"https://www.tiket.com/kereta-api/search?"
                   f"from={origin}&to={destination}&departDate={date}&adult={passengers}&child=0&infant=0")
            await page.goto(url, timeout=15000)
            await page.wait_for_timeout(4000)

            results = await page.evaluate("""
                () => {
                    const items = document.querySelectorAll('[class*="TrainCard"], [class*="train-item"]');
                    return Array.from(items).slice(0, 5).map(el => ({
                        name: el.querySelector('[class*="train-name"]')?.innerText || '',
                        depart: el.querySelector('[class*="depart-time"]')?.innerText || '',
                        arrive: el.querySelector('[class*="arrive-time"]')?.innerText || '',
                        price: el.querySelector('[class*="price"]')?.innerText || '0',
                        kelas: el.querySelector('[class*="class-name"]')?.innerText || 'Ekonomi',
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
                        "provider": "Tiket",
                        "train_name": r.get("name", "Unknown"),
                        "origin": origin, "destination": destination, "date": date,
                        "departure_time": r.get("depart", ""),
                        "arrival_time": r.get("arrive", ""),
                        "price": price, "currency": "IDR",
                        "seat_class": r.get("kelas", "Ekonomi"),
                    })
            return parsed if parsed else _mock(origin, destination, date)
    except Exception as e:
        logger.warning(f"[TiketScraper] {e}")
        return _mock(origin, destination, date)


def _mock(o, d, date):
    return [
        {"provider": "Tiket", "train_name": "Kertajaya", "origin": o, "destination": d,
         "date": date, "departure_time": "22:00", "arrival_time": "06:00",
         "price": 275000, "currency": "IDR", "seat_class": "Ekonomi"},
    ]
