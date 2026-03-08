"""
Airport code ↔ city name mapper for Indonesian airports.
Used to convert natural language city names to IATA codes and vice versa.
"""
from typing import Optional

# IATA code → (city_name, airport_name)
AIRPORT_DATA: dict[str, tuple[str, str]] = {
    # Java
    "CGK": ("Jakarta", "Soekarno-Hatta International"),
    "HLP": ("Jakarta", "Halim Perdanakusuma"),
    "SUB": ("Surabaya", "Juanda International"),
    "JOG": ("Yogyakarta", "Adisutjipto International"),
    "YIA": ("Yogyakarta", "Yogyakarta International"),
    "SOC": ("Solo", "Adi Soemarmo International"),
    "SRG": ("Semarang", "Ahmad Yani International"),
    "MLG": ("Malang", "Abdul Rachman Saleh"),
    "BDO": ("Bandung", "Husein Sastranegara"),
    # Bali & Nusa Tenggara
    "DPS": ("Bali", "Ngurah Rai International"),
    "LOP": ("Lombok", "International Lombok"),
    # Sumatra
    "MES": ("Medan", "Kualanamu International"),
    "PLM": ("Palembang", "Sultan Mahmud Badaruddin II"),
    "PKU": ("Pekanbaru", "Sultan Syarif Kasim II"),
    "BKS": ("Bengkulu", "Fatmawati Soekarno"),
    "BTH": ("Batam", "Hang Nadim"),
    "PGK": ("Pangkalpinang", "Depati Amir"),
    "TNJ": ("Tanjung Pinang", "Raja Haji Fisabilillah"),
    "DJB": ("Jambi", "Sultan Thaha"),
    "BTJ": ("Banda Aceh", "Sultan Iskandar Muda"),
    "SBG": ("Sabang", "Maimun Saleh"),
    "PDG": ("Padang", "Minangkabau International"),
    "LHI": ("Lampung", "Radin Inten II"),
    # Kalimantan
    "BPN": ("Balikpapan", "Sultan Aji Muhammad Sulaiman"),
    "BEJ": ("Berau", "Kalimarau"),
    "BDJ": ("Banjarmasin", "Syamsudin Noor"),
    "PKY": ("Palangkaraya", "Tjilik Riwut"),
    "PNK": ("Pontianak", "Supadio International"),
    "TRK": ("Tarakan", "Juwata"),
    # Sulawesi
    "UPG": ("Makassar", "Sultan Hasanuddin International"),
    "MDC": ("Manado", "Sam Ratulangi"),
    "PLW": ("Palu", "Mutiara"),
    "KDI": ("Kendari", "Haluoleo"),
    "TTR": ("Tana Toraja", "Pongtiku"),
    # Maluku & Papua
    "AMQ": ("Ambon", "Pattimura"),
    "TTE": ("Ternate", "Sultan Babullah"),
    "DJJ": ("Jayapura", "Sentani"),
    "MKQ": ("Merauke", "Mopah"),
    "TIM": ("Timika", "Moses Kilangin"),
    "MKW": ("Manokwari", "Rendani"),
    "SOQ": ("Sorong", "Domine Eduard Osok"),
}

# City name aliases (lowercase) → IATA code
CITY_ALIASES: dict[str, str] = {
    "jakarta": "CGK",
    "jkt": "CGK",
    "cengkareng": "CGK",
    "halim": "HLP",
    "surabaya": "SUB",
    "sby": "SUB",
    "juanda": "SUB",
    "yogyakarta": "JOG",
    "jogja": "JOG",
    "jogyakarta": "JOG",
    "yogya": "YIA",
    "yia": "YIA",
    "solo": "SOC",
    "semarang": "SRG",
    "malang": "MLG",
    "bandung": "BDO",
    "bali": "DPS",
    "denpasar": "DPS",
    "lombok": "LOP",
    "medan": "MES",
    "kualanamu": "MES",
    "palembang": "PLM",
    "pekanbaru": "PKU",
    "bengkulu": "BKS",
    "batam": "BTH",
    "pangkalpinang": "PGK",
    "tanjungpinang": "TNJ",
    "jambi": "DJB",
    "bandaaceh": "BTJ",
    "aceh": "BTJ",
    "padang": "PDG",
    "lampung": "LHI",
    "bandarlapmung": "LHI",
    "balikpapan": "BPN",
    "berau": "BEJ",
    "banjarmasin": "BDJ",
    "palangkaraya": "PKY",
    "pontianak": "PNK",
    "tarakan": "TRK",
    "makassar": "UPG",
    "ujungpandang": "UPG",
    "manado": "MDC",
    "palu": "PLW",
    "kendari": "KDI",
    "ambon": "AMQ",
    "ternate": "TTE",
    "jayapura": "DJJ",
    "merauke": "MKQ",
    "timika": "TIM",
    "manokwari": "MKW",
    "sorong": "SOQ",
}


def city_to_iata(city: str) -> Optional[str]:
    """Convert a city name or alias to IATA code."""
    key = city.lower().replace(" ", "").replace("-", "")
    # Already an IATA code?
    if city.upper() in AIRPORT_DATA:
        return city.upper()
    return CITY_ALIASES.get(key)


def iata_to_city(iata: str) -> Optional[str]:
    """Return city name for an IATA code."""
    data = AIRPORT_DATA.get(iata.upper())
    return data[0] if data else None


def iata_to_airport(iata: str) -> Optional[str]:
    """Return airport name for an IATA code."""
    data = AIRPORT_DATA.get(iata.upper())
    return data[1] if data else None


def all_iata_codes() -> list[str]:
    return list(AIRPORT_DATA.keys())
