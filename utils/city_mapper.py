"""
City ↔ KAI station code mapper for Indonesian train routes.
Used to convert natural language city names to KAI station codes.
"""
from typing import Optional

# Station code → (city_name, station_name)
STATION_DATA: dict[str, tuple[str, str]] = {
    # Jakarta
    "GMR": ("Jakarta", "Gambir"),
    "PSE": ("Jakarta", "Pasar Senen"),
    "JAKK": ("Jakarta", "Jakarta Kota"),
    "TNT": ("Jakarta", "Tanah Abang"),
    "MRI": ("Jakarta", "Manggarai"),
    # Java West
    "BD": ("Bandung", "Bandung"),
    "KAC": ("Bandung", "Kiaracondong"),
    "CM": ("Cirebon", "Cirebon"),
    "CNB": ("Cirebon", "Cirebon Prujakan"),
    "PWT": ("Purwokerto", "Purwokerto"),
    "KT": ("Kroya", "Kroya"),
    # Java Central
    "SMC": ("Semarang", "Semarang Tawang"),
    "PNR": ("Semarang", "Poncol"),
    "YK": ("Yogyakarta", "Yogyakarta"),
    "LPN": ("Yogyakarta", "Lempuyangan"),
    "SLO": ("Solo", "Solo Balapan"),
    "STA": ("Solo", "Purwosari"),
    "MTN": ("Madiun", "Madiun"),
    # Java East
    "KD": ("Kediri", "Kediri"),
    "BL": ("Blitar", "Blitar"),
    "MLG": ("Malang", "Malang"),
    "KAL": ("Malang", "Kepanjen"),
    "MN": ("Mojokerto", "Mojokerto"),
    "SBI": ("Surabaya", "Surabaya Gubeng"),
    "SBP": ("Surabaya", "Surabaya Pasar Turi"),
    "SGU": ("Surabaya", "Surabaya Kota"),
    "SWL": ("Surabaya", "Wonokromo"),
    "SDI": ("Sidoarjo", "Sidoarjo"),
    "BJN": ("Bojonegoro", "Bojonegoro"),
    "PB": ("Probolinggo", "Probolinggo"),
    "JR": ("Jember", "Jember"),
    "BJW": ("Banyuwangi", "Banyuwangi Baru"),
    # Sumatra
    "TJ": ("Tanjung Karang", "Tanjung Karang"),
    "PLD": ("Palembang", "Kertapati"),
    "LBH": ("Lubuklinggau", "Lubuklinggau"),
    "MDN": ("Medan", "Medan"),
    "TBI": ("Tanjungbalai", "Tanjungbalai"),
    "PRP": ("Pematangsiantar", "Pematangsiantar"),
    "PDG": ("Padang", "Padang"),
    "PDG2": ("Padang", "Pauh Lima"),
    "BKT": ("Bukittinggi", "Bukittinggi"),
}

# City alias → station code
CITY_STATION_ALIASES: dict[str, str] = {
    "jakarta": "GMR",
    "jkt": "GMR",
    "gambir": "GMR",
    "pasarsenen": "PSE",
    "senen": "PSE",
    "bandung": "BD",
    "cirebon": "CM",
    "purwokerto": "PWT",
    "semarang": "SMC",
    "yogyakarta": "YK",
    "jogja": "YK",
    "jogyakarta": "YK",
    "yogya": "YK",
    "solo": "SLO",
    "solokencohan": "SLO",
    "surakarta": "SLO",
    "madiun": "MTN",
    "kediri": "KD",
    "blitar": "BL",
    "malang": "MLG",
    "surabaya": "SBI",
    "sby": "SBI",
    "gubeng": "SBI",
    "pasarturi": "SBP",
    "sidoarjo": "SDI",
    "bojonegoro": "BJN",
    "probolinggo": "PB",
    "jember": "JR",
    "banyuwangi": "BJW",
    "lampung": "TJ",
    "tanjungkarang": "TJ",
    "bandarlampung": "TJ",
    "palembang": "PLD",
    "lubuklinggau": "LBH",
    "medan": "MDN",
    "padang": "PDG",
}


def city_to_station(city: str) -> Optional[str]:
    """Return KAI station code for a city name."""
    key = city.lower().replace(" ", "").replace("-", "")
    if city.upper() in STATION_DATA:
        return city.upper()
    return CITY_STATION_ALIASES.get(key)


def station_to_city(code: str) -> Optional[str]:
    """Return city name for a station code."""
    data = STATION_DATA.get(code.upper())
    return data[0] if data else None


def station_to_name(code: str) -> Optional[str]:
    """Return station name for a station code."""
    data = STATION_DATA.get(code.upper())
    return data[1] if data else None


def all_station_codes() -> list[str]:
    return list(STATION_DATA.keys())
