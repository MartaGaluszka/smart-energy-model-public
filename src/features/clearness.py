"""
Clear-sky index (clearness) — Haurwitz GHI + elevacja astral.

CS4 = production 16 + cloud_cover_low/mid + clearness
(clearness = radiation_wm2 / ghi_clear, clip 0–1.5)
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import pytz
from astral import LocationInfo
from astral.sun import elevation


def haurwitz_ghi_wm2(cos_zenith: float) -> float:
    """Clear-sky GHI [W/m²] — model Haurwitz (bez pvlib)."""
    if cos_zenith <= 0:
        return 0.0
    return float(1098.0 * (cos_zenith ** 1.006) * np.exp(-0.057 / cos_zenith))


def _elevation_deg(
    day: str,
    hour: float,
    latitude: float,
    longitude: float,
    timezone_str: str = 'Europe/Warsaw',
) -> float:
    tz = pytz.timezone(timezone_str)
    loc = LocationInfo(latitude=latitude, longitude=longitude, timezone=timezone_str)
    h = int(hour)
    m = int(round((hour - h) * 60))
    dt = tz.localize(datetime.fromisoformat(f'{day}T{h:02d}:{m:02d}:00'))
    return float(elevation(loc.observer, dt))


def add_clearness_features(
    df: pd.DataFrame,
    *,
    latitude: float = 50.06,
    longitude: float = 19.94,
    radiation_col: str = 'radiation_wm2',
    clip_max: float = 1.5,
) -> pd.DataFrame:
    """Dodaj ``ghi_clear_wm2`` i ``clearness`` (wymaga kolumn day, hour, radiation)."""
    out = df.copy()
    if radiation_col not in out.columns:
        out['ghi_clear_wm2'] = np.nan
        out['clearness'] = np.nan
        return out

    cache: dict[tuple[str, int], float] = {}

    def elev_for_row(row) -> float:
        day = str(row['day'])
        hour_i = int(row['hour'])
        key = (day, hour_i)
        if key not in cache:
            cache[key] = _elevation_deg(day, float(row['hour']), latitude, longitude)
        return cache[key]

    elev = out.apply(elev_for_row, axis=1)
    cos_z = np.sin(np.deg2rad(elev.to_numpy(dtype=float)))
    cos_z = np.clip(cos_z, 0.0, None)
    ghi = np.array([haurwitz_ghi_wm2(float(c)) for c in cos_z], dtype=float)
    out['ghi_clear_wm2'] = ghi
    rad = pd.to_numeric(out[radiation_col], errors='coerce').to_numpy(dtype=float)
    with np.errstate(divide='ignore', invalid='ignore'):
        clearness = np.where(ghi > 5.0, rad / ghi, np.nan)
    out['clearness'] = np.clip(clearness, 0.0, clip_max)
    # Braki → mediana dnia / 0.7 (umiarkowane niebo)
    out['clearness'] = (
        out.groupby('day')['clearness']
        .transform(lambda s: s.fillna(s.median()))
        .fillna(0.7)
    )
    return out
