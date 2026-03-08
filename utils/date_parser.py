"""
Smart Date Parser – comprehensive Indonesian date phrase parser.

Handles:
  besok, lusa, malam ini, hari ini
  minggu depan, minggu ini, akhir pekan
  tanggal 12, tgl 15
  dd/mm/yyyy, dd-mm-yyyy, yyyy-mm-dd
  Month names: januari, februari … desember
  Relative: 3 hari lagi, 2 minggu lagi

Always returns an ISO date string: YYYY-MM-DD

File: utils/date_parser.py
"""
import re
from datetime import datetime, timedelta
from typing import Optional

MONTHS_ID = {
    "januari": 1,  "jan": 1,
    "februari": 2, "feb": 2,
    "maret": 3,    "mar": 3,
    "april": 4,    "apr": 4,
    "mei": 5,
    "juni": 6,     "jun": 6,
    "juli": 7,     "jul": 7,
    "agustus": 8,  "agt": 8, "aug": 8,
    "september": 9,"sep": 9,
    "oktober": 10, "okt": 10, "oct": 10,
    "november": 11,"nov": 11,
    "desember": 12,"des": 12, "dec": 12,
}

DAYS_ID = {
    "senin": 0, "selasa": 1, "rabu": 2,
    "kamis": 3, "jumat": 4, "jum'at": 4,
    "sabtu": 5, "minggu": 6, "ahad": 6,
}

WORD_NUMS = {
    "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
    "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9, "sepuluh": 10,
    "sebelas": 11, "dua belas": 12,
}


def parse_date(text: str, reference: Optional[datetime] = None) -> str:
    """
    Extract a date from Indonesian natural language text.

    Args:
        text: Source text (may contain other words).
        reference: Reference datetime (defaults to now).

    Returns:
        ISO date string "YYYY-MM-DD".
    """
    today = reference or datetime.now()
    today = today.replace(hour=0, minute=0, second=0, microsecond=0)
    low = text.lower().strip()

    result = (
        _parse_iso(low, today)
        or _parse_dmy(low, today)
        or _parse_keyword(low, today)
        or _parse_day_name(low, today)
        or _parse_relative_days(low, today)
        or _parse_tanggal(low, today)
        or _parse_month_name(low, today)
    )

    if result:
        return result.strftime("%Y-%m-%d")

    # Default: tomorrow
    return (today + timedelta(days=1)).strftime("%Y-%m-%d")


# ─── Parsers (in order of priority) ──────────────────────────────────────────

def _parse_iso(text: str, today: datetime) -> Optional[datetime]:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d")
        except ValueError:
            pass
    return None


def _parse_dmy(text: str, today: datetime) -> Optional[datetime]:
    """DD/MM/YYYY or DD-MM-YYYY or D MM YYYY formats."""
    m = re.search(r"(\d{1,2})[/\-\s](\d{1,2})[/\-\s](\d{4})", text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(y, mo, d)
        except ValueError:
            pass
    return None


def _parse_keyword(text: str, today: datetime) -> Optional[datetime]:
    """Fixed keyword phrases."""
    if any(k in text for k in ("hari ini", "malam ini", "today", "sekarang")):
        return today
    if any(k in text for k in ("besok", "tomorrow", "esok hari", "esok")):
        return today + timedelta(days=1)
    if any(k in text for k in ("lusa", "day after tomorrow")):
        return today + timedelta(days=2)
    if any(k in text for k in ("minggu depan", "next week", "pekan depan")):
        return today + timedelta(days=7)
    if any(k in text for k in ("akhir pekan", "weekend", "sabtu ini", "sabtu depan")):
        days = (5 - today.weekday()) % 7 or 7
        return today + timedelta(days=days)
    if "minggu ini" in text or "ahad ini" in text:
        days = (6 - today.weekday()) % 7 or 7
        return today + timedelta(days=days)
    if "bulan depan" in text or "next month" in text:
        # First day of next month
        if today.month == 12:
            return today.replace(year=today.year + 1, month=1, day=1)
        return today.replace(month=today.month + 1, day=1)
    return None


def _parse_day_name(text: str, today: datetime) -> Optional[datetime]:
    """'rabu' / 'jumat depan' → next occurrence of that weekday."""
    for name, weekday in DAYS_ID.items():
        if name in text:
            days_ahead = (weekday - today.weekday()) % 7 or 7
            return today + timedelta(days=days_ahead)
    return None


def _parse_relative_days(text: str, today: datetime) -> Optional[datetime]:
    """'3 hari lagi', 'dua minggu lagi', '2 bulan lagi'."""
    # numeric
    m = re.search(r"(\d+)\s*(hari|minggu|bulan)\s*(lagi|kemudian|ke depan|mendatang)?", text)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        if unit == "hari":
            return today + timedelta(days=n)
        if unit == "minggu":
            return today + timedelta(weeks=n)
        if unit == "bulan":
            month = today.month + n
            year = today.year + (month - 1) // 12
            month = (month - 1) % 12 + 1
            return today.replace(year=year, month=month)

    # word numbers
    for word, n in WORD_NUMS.items():
        pattern = rf"{re.escape(word)}\s*(hari|minggu|bulan)\s*(lagi|kemudian)?"
        m = re.search(pattern, text)
        if m:
            unit = m.group(1)
            if unit == "hari":
                return today + timedelta(days=n)
            if unit == "minggu":
                return today + timedelta(weeks=n)

    return None


def _parse_tanggal(text: str, today: datetime) -> Optional[datetime]:
    """'tanggal 12', 'tgl 15', 'tanggal 5 april'."""
    # With month name
    m = re.search(
        r"(?:tanggal|tgl)\s+(\d{1,2})\s+(" + "|".join(MONTHS_ID) + r")",
        text
    )
    if m:
        day, month_name = int(m.group(1)), MONTHS_ID[m.group(2)]
        year = today.year if month_name >= today.month else today.year + 1
        try:
            return datetime(year, month_name, day)
        except ValueError:
            pass

    # Bare day number
    m = re.search(r"(?:tanggal|tgl)\s+(\d{1,2})", text)
    if m:
        day = int(m.group(1))
        candidate = today.replace(day=day) if day >= today.day else (
            (today.replace(day=28) + timedelta(days=4)).replace(day=day)
        )
        try:
            return candidate
        except ValueError:
            pass

    return None


def _parse_month_name(text: str, today: datetime) -> Optional[datetime]:
    """'5 april', '12 desember 2026'."""
    pattern = r"(\d{1,2})\s+(" + "|".join(MONTHS_ID) + r")(?:\s+(\d{4}))?"
    m = re.search(pattern, text)
    if m:
        day = int(m.group(1))
        month = MONTHS_ID[m.group(2)]
        year = int(m.group(3)) if m.group(3) else (
            today.year if month >= today.month else today.year + 1
        )
        try:
            return datetime(year, month, day)
        except ValueError:
            pass
    return None
