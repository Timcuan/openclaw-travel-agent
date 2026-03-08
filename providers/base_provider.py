"""
Base Provider – abstract interface all travel providers must implement.

Every provider (train, flight, hotel) inherits from Provider
and implements search() and optionally book().

File: providers/base_provider.py
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, ClassVar, Optional


@dataclass
class NormalizedResult:
    """
    Canonical result schema returned by every provider.

    All providers MUST return NormalizedResult objects.
    """
    travel_type: str            # "train" | "flight" | "hotel"
    provider: str               # Provider name (e.g. "KAI", "Amadeus")
    name: str                   # Train name / Flight number / Hotel name
    origin: str = ""            # Origin city / code
    destination: str = ""       # Destination city / code
    city: str = ""              # Hotel city
    date: str = ""              # Travel date YYYY-MM-DD / check-in
    check_in: str = ""
    check_out: str = ""
    departure: str = ""         # HH:MM
    arrival: str = ""           # HH:MM
    duration: str = ""          # "8j 30m"
    price: float = 0.0          # Price in IDR
    currency: str = "IDR"
    seat_class: str = ""        # ekonomi / bisnis / eksekutif
    star_rating: int = 0        # hotel stars
    review_score: float = 0.0   # hotel review score
    breakfast_included: bool = False
    available_seats: Optional[int] = None
    cancellation_policy: str = ""
    image_url: str = ""
    provider_ref: str = ""      # internal booking reference from provider
    raw: dict = field(default_factory=dict, repr=False)  # original payload

    def to_dict(self) -> dict:
        """
        Return a dict using the provider-compatible field names expected by
        cheapest_engine, deal_detector, and the message formatters.
        """
        base = {
            "travel_type":   self.travel_type,
            "provider":      self.provider,
            "date":          self.date,
            "price":         self.price,
            "currency":      self.currency,
            "provider_ref":  self.provider_ref,
        }

        if self.travel_type == "train":
            base.update({
                "train_name":     self.name,
                "origin":         self.origin,
                "destination":    self.destination,
                "departure_time": self.departure,
                "arrival_time":   self.arrival,
                "duration":       self.duration,
                "seat_class":     self.seat_class,
                "available_seats": self.available_seats,
            })
        elif self.travel_type == "flight":
            # name is "GA GA-001" – split into airline + number
            parts = self.name.split(None, 1)
            base.update({
                "airline":        parts[0] if parts else self.name,
                "flight_number":  parts[1] if len(parts) > 1 else "",
                "origin":         self.origin,
                "destination":    self.destination,
                "departure_time": self.departure,
                "arrival_time":   self.arrival,
                "duration":       self.duration,
                "seat_class":     self.seat_class,
            })
        elif self.travel_type == "hotel":
            base.update({
                "hotel_name":          self.name,
                "city":                self.city,
                "check_in":            self.check_in,
                "check_out":           self.check_out,
                "price_per_night":     self.price,
                "star_rating":         self.star_rating,
                "review_score":        self.review_score,
                "breakfast_included":  self.breakfast_included,
                "cancellation_policy": self.cancellation_policy,
                "image_url":           self.image_url,
            })

        # Remove None values to keep dicts lean
        return {k: v for k, v in base.items() if v is not None and v != ""}


class Provider(ABC):
    """
    Abstract base class for all travel providers.

    Class attributes:
        name: Human-readable provider name (e.g. "KAI")
        travel_type: "train" | "flight" | "hotel"
        priority: Lower = higher priority when merging results (1 = highest)
    """
    name: ClassVar[str] = "BaseProvider"
    travel_type: ClassVar[str] = "unknown"
    priority: ClassVar[int] = 99

    def __init__(self, config: dict | None = None):
        """
        Args:
            config: Dict from providers.yaml section for this provider.
                    e.g. {"enabled": true, "api_key": "xxx"}
        """
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self._setup()

    def _setup(self):
        """Optional hook for subclass initialization."""
        pass

    @abstractmethod
    async def search(self, params: dict) -> list[NormalizedResult]:
        """
        Execute a travel search.

        Args:
            params: Search parameters dict. Keys vary by travel_type:
                train/flight: origin, destination, date, passengers
                hotel: city, check_in, check_out, adults, rooms

        Returns:
            List of NormalizedResult objects.
        """
        ...

    async def book(self, result: NormalizedResult, passenger: dict) -> dict:
        """
        Initiate booking for a result. Override in providers that support it.

        Returns:
            Dict with keys: success (bool), booking_ref (str), message (str)
        """
        return {
            "success": False,
            "booking_ref": "",
            "message": f"Booking via {self.name} not yet implemented.",
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} enabled={self.enabled}>"
