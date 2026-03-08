"""Booking.com Hotel Provider plugin. File: providers/hotel/booking_provider.py"""
from providers.base_provider import Provider, NormalizedResult
from utils.logger import logger


class BookingProvider(Provider):
    name = "Booking.com"
    travel_type = "hotel"
    priority = 2

    async def search(self, params: dict) -> list[NormalizedResult]:
        try:
            from providers.hotel.booking_adapter import booking_search_hotels
            raw = await booking_search_hotels(
                params.get("city", ""), params.get("check_in", ""),
                params.get("check_out", ""), params.get("adults", 2), params.get("rooms", 1),
            )
            from services.result_normalizer import normalize_hotel
            return [normalize_hotel(r, "Booking.com") for r in raw]
        except Exception as e:
            logger.error(f"[BookingProvider] {e}")
            return []
