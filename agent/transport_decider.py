"""
Transport Decider – smart recommendation of train vs flight based on
route distance and travel time.

Rule:
  distance < 800 km  → recommend train (faster door-to-door, cheaper)
  distance >= 800 km → recommend flight

File: agent/transport_decider.py
"""
from dataclasses import dataclass
from typing import Optional
from utils.logger import logger

# ─── Approximate inter-city distances (km) ────────────────────────────────────
# Straight-line, used only for recommendation – not routing.

CITY_DISTANCES: dict[tuple[str, str], int] = {
    # Java corridor
    ("jakarta", "bandung"): 120,
    ("jakarta", "cirebon"): 250,
    ("jakarta", "semarang"): 450,
    ("jakarta", "yogyakarta"): 510,
    ("jakarta", "solo"): 560,
    ("jakarta", "surabaya"): 780,
    ("jakarta", "malang"): 820,
    ("jakarta", "banyuwangi"): 1050,
    ("bandung", "yogyakarta"): 400,
    ("bandung", "surabaya"): 690,
    ("yogyakarta", "surabaya"): 310,
    ("yogyakarta", "malang"): 280,
    ("surabaya", "malang"): 90,
    ("surabaya", "banyuwangi"): 290,
    # Cross-island
    ("jakarta", "bali"): 1100,
    ("jakarta", "medan"): 1700,
    ("jakarta", "makassar"): 1800,
    ("jakarta", "balikpapan"): 1600,
    ("jakarta", "manado"): 2100,
    ("jakarta", "jayapura"): 3700,
    ("surabaya", "bali"): 340,
    ("surabaya", "makassar"): 1400,
    ("surabaya", "medan"): 1900,
    ("bandung", "bali"): 1000,
    ("yogyakarta", "bali"): 900,
    ("bali", "makassar"): 1200,
    ("bali", "jayapura"): 2900,
    ("medan", "jakarta"): 1700,
    ("makassar", "jakarta"): 1800,
}

TRAIN_THRESHOLD_KM = 800


@dataclass
class TransportDecision:
    recommended: str          # "train" | "flight" | "either"
    alternative: Optional[str]
    distance_km: Optional[int]
    reason: str
    show_both: bool = False   # True when distance is near the threshold


def decide(origin: str, destination: str) -> TransportDecision:
    """
    Recommend the best transport mode for a given city pair.

    Args:
        origin: City name (lowercase).
        destination: City name (lowercase).

    Returns:
        TransportDecision with recommendation and reasoning.
    """
    o = origin.lower().strip()
    d = destination.lower().strip()

    distance = _get_distance(o, d)

    if distance is None:
        # Unknown route – default to train for domestic, show both
        return TransportDecision(
            recommended="train",
            alternative="flight",
            distance_km=None,
            reason="Rute tidak diketahui. Showing kereta & pesawat.",
            show_both=True,
        )

    if distance < TRAIN_THRESHOLD_KM:
        return TransportDecision(
            recommended="train",
            alternative="flight",
            distance_km=distance,
            reason=f"Jarak {distance} km – kereta lebih cepat & hemat.",
            show_both=False,
        )

    if distance <= TRAIN_THRESHOLD_KM + 100:
        # Borderline – show both
        return TransportDecision(
            recommended="train",
            alternative="flight",
            distance_km=distance,
            reason=f"Jarak {distance} km – kereta dan pesawat tersedia.",
            show_both=True,
        )

    return TransportDecision(
        recommended="flight",
        alternative="train",
        distance_km=distance,
        reason=f"Jarak {distance} km – pesawat lebih efisien.",
        show_both=False,
    )


def _get_distance(a: str, b: str) -> Optional[int]:
    """Look up distance in both directions."""
    return (
        CITY_DISTANCES.get((a, b))
        or CITY_DISTANCES.get((b, a))
    )


def format_decision(decision: TransportDecision) -> str:
    """Return a short one-line suggestion string."""
    if decision.recommended == "train":
        emoji = "🚂"
    else:
        emoji = "✈️"

    if decision.distance_km:
        dist = f" (~{decision.distance_km} km)"
    else:
        dist = ""

    return f"{emoji} {decision.reason}{dist}"
