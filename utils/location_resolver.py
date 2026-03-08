"""
Location Resolver – unified city → station/airport/hotel-city resolver.

Provides:
    resolve_train_station(city) → station code (KAI)
    resolve_airport(city)       → IATA code
    resolve_hotel_city(city)    → canonical city name for hotel APIs

Falls back to fuzzy matching when exact match fails.

File: utils/location_resolver.py
"""
from typing import Optional
from utils.logger import logger

# ─── Ordered list of Indonesian cities (used by NLP city extractor) ───────────

INDONESIAN_CITIES = [
    # Java
    "jakarta", "surabaya", "bandung", "yogyakarta", "jogja", "jogyakarta",
    "semarang", "malang", "solo", "surakarta", "madiun", "kediri", "blitar",
    "jember", "banyuwangi", "probolinggo", "sidoarjo", "bojonegoro",
    "cirebon", "purwokerto", "tasikmalaya", "serang", "tangerang",
    "bekasi", "depok", "bogor",
    # Bali & NTB
    "bali", "denpasar", "lombok", "mataram",
    # Sumatra
    "medan", "palembang", "pekanbaru", "padang", "banda aceh", "aceh",
    "lampung", "bandar lampung", "jambi", "bengkulu", "batam",
    "tanjungpinang", "pangkalpinang", "lubuklinggau",
    # Kalimantan
    "balikpapan", "banjarmasin", "pontianak", "palangkaraya", "tarakan", "berau",
    # Sulawesi
    "makassar", "manado", "palu", "kendari", "gorontalo",
    # Maluku & Papua
    "ambon", "ternate", "jayapura", "merauke", "sorong", "manokwari", "timika",
    # Codes / abbreviations
    "sby", "jkt", "bdg", "yk", "smg",
]


# ─── Train station mapping ────────────────────────────────────────────────────

TRAIN_STATION_MAP: dict[str, str] = {
    # Jakarta
    "jakarta": "GMR",       "jkt": "GMR",       "gambir": "GMR",
    "pasarsenen": "PSE",    "senen": "PSE",
    # West Java
    "bandung": "BD",        "bdg": "BD",
    "cirebon": "CM",
    "purwokerto": "PWT",
    "bogor": "BOO",
    "tasikmalaya": "TSM",
    "serang": "SRG",
    # Central Java
    "semarang": "SMC",      "smg": "SMC",
    "yogyakarta": "YK",     "jogja": "YK",      "jogyakarta": "YK",     "yk": "YK",
    "solo": "SLO",          "surakarta": "SLO",
    "madiun": "MTN",
    "purwosari": "PWS",
    # East Java
    "surabaya": "SBI",      "sby": "SBI",
    "sidoarjo": "SDI",
    "malang": "MLG",
    "kediri": "KD",
    "blitar": "BL",
    "jember": "JR",
    "banyuwangi": "BJW",
    "probolinggo": "PB",
    "bojonegoro": "BJN",
    "mojokerto": "MN",
    # Sumatra
    "medan": "MDN",
    "padang": "PDG",
    "palembang": "PLD",
    "lubuklinggau": "LBH",
    "bandar lampung": "TJ",
    "lampung": "TJ",
    "tanjungkarang": "TJ",
}


# ─── Airport (IATA) mapping ───────────────────────────────────────────────────

AIRPORT_MAP: dict[str, str] = {
    # Java
    "jakarta": "CGK",       "jkt": "CGK",       "cengkareng": "CGK",
    "halim": "HLP",
    "surabaya": "SUB",      "sby": "SUB",
    "yogyakarta": "JOG",    "jogja": "JOG",      "jogyakarta": "JOG",
    "yia": "YIA",           "kulon progo": "YIA",
    "solo": "SOC",          "surakarta": "SOC",
    "semarang": "SRG",
    "malang": "MLG",
    "bandung": "BDO",
    # Bali & NTB
    "bali": "DPS",          "denpasar": "DPS",
    "lombok": "LOP",        "mataram": "LOP",
    # Sumatra
    "medan": "MES",         "kualanamu": "MES",
    "palembang": "PLM",
    "pekanbaru": "PKU",
    "padang": "PDG",
    "banda aceh": "BTJ",    "aceh": "BTJ",
    "batam": "BTH",
    "tanjungpinang": "TNJ",
    "pangkalpinang": "PGK",
    "lampung": "TKG",       "bandar lampung": "TKG",
    "jambi": "DJB",
    "bengkulu": "BKS",
    # Kalimantan
    "balikpapan": "BPN",
    "banjarmasin": "BDJ",
    "pontianak": "PNK",
    "palangkaraya": "PKY",
    "tarakan": "TRK",
    "berau": "BEJ",
    # Sulawesi
    "makassar": "UPG",      "ujungpandang": "UPG",
    "manado": "MDC",
    "palu": "PLW",
    "kendari": "KDI",
    "gorontalo": "GTO",
    # Maluku & Papua
    "ambon": "AMQ",
    "ternate": "TTE",
    "jayapura": "DJJ",
    "merauke": "MKQ",
    "sorong": "SOQ",
    "manokwari": "MKW",
    "timika": "TIM",
}


# ─── Hotel city canonical names ───────────────────────────────────────────────

HOTEL_CITY_MAP: dict[str, str] = {
    "jakarta": "Jakarta", "jkt": "Jakarta",
    "surabaya": "Surabaya", "sby": "Surabaya",
    "bandung": "Bandung", "bdg": "Bandung",
    "yogyakarta": "Yogyakarta", "jogja": "Yogyakarta", "jogyakarta": "Yogyakarta",
    "semarang": "Semarang",
    "malang": "Malang",
    "solo": "Solo",
    "bali": "Bali", "denpasar": "Bali",
    "lombok": "Lombok", "mataram": "Lombok",
    "medan": "Medan",
    "palembang": "Palembang",
    "pekanbaru": "Pekanbaru",
    "padang": "Padang",
    "balikpapan": "Balikpapan",
    "banjarmasin": "Banjarmasin",
    "pontianak": "Pontianak",
    "makassar": "Makassar",
    "manado": "Manado",
    "batam": "Batam",
    "lampung": "Lampung", "bandar lampung": "Bandarlampung",
    "ambon": "Ambon",
    "jayapura": "Jayapura",
}


# ─── Resolver functions ───────────────────────────────────────────────────────

def resolve_train_station(city: str) -> Optional[str]:
    """
    Resolve a city name to KAI station code.

    Args:
        city: City name or alias (case-insensitive).

    Returns:
        Station code string (e.g. "GMR") or None if not found.
    """
    if not city:
        return None
    key = city.lower().strip().replace("-", " ")
    # Direct map
    result = TRAIN_STATION_MAP.get(key)
    if result:
        return result
    # Try prefix match
    for k, v in TRAIN_STATION_MAP.items():
        if k.startswith(key) or key.startswith(k):
            return v
    logger.warning(f"[LocationResolver] Unknown train station: {city!r}")
    return city.upper()[:3]  # best-effort fallback


def resolve_airport(city: str) -> Optional[str]:
    """
    Resolve a city name to IATA airport code.

    Args:
        city: City name or alias (case-insensitive).

    Returns:
        IATA code string (e.g. "CGK") or None if not found.
    """
    if not city:
        return None
    key = city.lower().strip().replace("-", " ")
    result = AIRPORT_MAP.get(key)
    if result:
        return result
    # Try prefix
    for k, v in AIRPORT_MAP.items():
        if k.startswith(key) or key.startswith(k):
            return v
    logger.warning(f"[LocationResolver] Unknown airport: {city!r}")
    return city.upper()[:3]


def resolve_hotel_city(city: str) -> str:
    """
    Resolve city name to canonical hotel search city name.

    Args:
        city: City name or alias.

    Returns:
        Canonical city name (e.g. "Yogyakarta") or original capitalised.
    """
    if not city:
        return ""
    key = city.lower().strip()
    result = HOTEL_CITY_MAP.get(key)
    if result:
        return result
    # Prefix
    for k, v in HOTEL_CITY_MAP.items():
        if k.startswith(key):
            return v
    return city.capitalize()
