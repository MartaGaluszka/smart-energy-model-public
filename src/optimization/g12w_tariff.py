"""
Taryfa G12w (dwustrefowa weekendowa) — klasyfikacja stref i okna ładowania baterii.

Strefa tania (pozaszczytowa, zone2):
  - pon–pt: 22:00–6:00 oraz zazwyczaj 13:00–15:00
  - sob–nd i dni ustawowo wolne: cała doba

Strefa droga (szczytowa, zone1):
  - pon–pt: 6:00–13:00 oraz 15:00–22:00
"""

from datetime import date, datetime, time
from typing import Iterable, Literal, Optional, Union

Zone = Literal[1, 2]  # 1 = szczyt (droższa), 2 = pozaszczyt (tańsza)

TARIFF_NAME = 'G12w'

# Pon–pt: godziny taniej strefy (poza weekendem/świętem)
CHEAP_WEEKDAY_NIGHT = (22, 6)       # 22:00–6:00 → h>=22 lub h<6
CHEAP_WEEKDAY_MIDDAY = (13, 15)     # 13:00–15:00 → 13<=h<15

# Dni ustawowo wolne w PL (stałe daty; Wielkanoc/ruchome — uzupełniaj rocznie)
PL_PUBLIC_HOLIDAYS: set[date] = {
    date(2025, 1, 1), date(2025, 1, 6), date(2025, 4, 20), date(2025, 4, 21),
    date(2025, 5, 1), date(2025, 5, 3), date(2025, 6, 19), date(2025, 8, 15),
    date(2025, 11, 1), date(2025, 11, 11), date(2025, 12, 25), date(2025, 12, 26),
    date(2026, 1, 1), date(2026, 1, 6), date(2026, 4, 5), date(2026, 4, 6),
    date(2026, 5, 1), date(2026, 5, 3), date(2026, 6, 11), date(2026, 8, 15),
    date(2026, 11, 1), date(2026, 11, 11), date(2026, 12, 25), date(2026, 12, 26),
}


def is_public_holiday(d: date, extra_holidays: Optional[Iterable[date]] = None) -> bool:
    if d in PL_PUBLIC_HOLIDAYS:
        return True
    if extra_holidays and d in set(extra_holidays):
        return True
    return False


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def is_cheap_zone(dt: Union[datetime, date], hour: Optional[int] = None) -> bool:
    """
    True = strefa tania (pozaszczytowa, zone2).

    Przy samym `date` (bez godziny) — cała doba tania w weekend/święto, inaczej False.
    """
    if isinstance(dt, datetime):
        d, h = dt.date(), dt.hour
    else:
        d, h = dt, hour

    if is_weekend(d) or is_public_holiday(d):
        return True if h is None else True

    if h is None:
        return False

    if h >= CHEAP_WEEKDAY_NIGHT[0] or h < CHEAP_WEEKDAY_NIGHT[1]:
        return True
    if CHEAP_WEEKDAY_MIDDAY[0] <= h < CHEAP_WEEKDAY_MIDDAY[1]:
        return True
    return False


def classify_zone(dt: Union[datetime, date], hour: Optional[int] = None) -> Zone:
    """1 = szczyt (droższa), 2 = pozaszczyt (tańsza)."""
    return 2 if is_cheap_zone(dt, hour=hour) else 1


def cheap_zone_label(zone: Zone) -> str:
    return 'pozaszczyt (tańsza)' if zone == 2 else 'szczyt (droższa)'


def weekday_force_charge_windows() -> list[tuple[time, time]]:
    """Okna do ForceCharge w FoxESS — tania strefa, dni robocze."""
    return [
        (time(22, 0), time(6, 0)),   # noc (przechodzi przez północ)
        (time(13, 0), time(15, 0)),  # ~2 h w ciągu dnia (zima: arbitraż taryfowy)
    ]


def tariff_summary() -> str:
    return (
        'G12w dwustrefowa weekendowa: tanio pon–pt 22:00–6:00 i 13:00–15:00; '
        'cała doba w weekendy i święta. Drogo pon–pt 6:00–13:00 i 15:00–22:00.'
    )
