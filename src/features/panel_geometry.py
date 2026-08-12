"""
Geometria paneli PV — tilt / azymut → cechy kąta padania i przybliżonej POA.

Domyślnie WYŁĄCZONE w modelu produkcyjnym (16 cech).
Po ~7 dniach obserwacji: włącz PANEL_GEOMETRY_FEATURES=1, porównaj
scripts/compare_model_change.py, potem ewentualnie dodaj do PRODUCTION.

Instalacja (domyślnie):
  PANEL_TILT_DEG=35          # ~70% nachylenia dachu
  PANEL_AZIMUTH_DEG=180      # 180 = południe (0=N, 90=E, 180=S, 270=W)
"""

from __future__ import annotations

import os
from datetime import datetime

import numpy as np
import pandas as pd
import pytz
from astral import LocationInfo
from astral.sun import azimuth as sun_azimuth
from astral.sun import elevation as sun_elevation

# Kolumny do eksperymentu (nie w HOURLY_FEATURE_COLUMNS_PRODUCTION)
PANEL_GEOMETRY_COLUMNS = [
    'sun_elevation_deg',
    'sun_azimuth_deg',
    'incidence_cos',
    'poa_approx_wm2',
]


def panel_geometry_enabled() -> bool:
    return os.getenv('PANEL_GEOMETRY_FEATURES', '0').strip().lower() in ('1', 'true', 'yes')


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, '').strip()
    return float(raw) if raw else default


def get_panel_params() -> tuple[float, float]:
    """(tilt_deg, azimuth_deg) — południe=180, tilt domyślnie 35°."""
    tilt = _env_float('PANEL_TILT_DEG', 35.0)
    azimuth = _env_float('PANEL_AZIMUTH_DEG', 180.0)
    return tilt, azimuth


def _solar_angles_for_hour(
    day: str,
    hour: int,
    latitude: float,
    longitude: float,
    timezone_str: str = 'Europe/Warsaw',
) -> tuple[float, float]:
    """Wysokość i azymut słońca w środku godziny lokalnej."""
    tz = pytz.timezone(timezone_str)
    loc = LocationInfo(latitude=latitude, longitude=longitude, timezone=timezone_str)
    dt = tz.localize(datetime.fromisoformat(f'{day}T{hour:02d}:30:00'))
    elev = float(sun_elevation(loc.observer, dt))
    az = float(sun_azimuth(loc.observer, dt))
    return elev, az


def incidence_cosine(
    sun_elev_deg: float,
    sun_az_deg: float,
    tilt_deg: float,
    panel_az_deg: float,
) -> float:
    """
    cos(θ) kąta padania na płaszczyznę paneli (0 gdy słońce za panelem / pod horyzontem).

    θ = kąt między normalną do paneli a kierunkiem do słońca.
    """
    if sun_elev_deg <= 0:
        return 0.0

    beta = np.radians(tilt_deg)
    gamma = np.radians(panel_az_deg)
    elev = np.radians(sun_elev_deg)
    az = np.radians(sun_az_deg)
    zenith = np.pi / 2 - elev

    cos_i = (
        np.cos(zenith) * np.cos(beta)
        + np.sin(zenith) * np.sin(beta) * np.cos(az - gamma)
    )
    return float(np.clip(cos_i, 0.0, 1.0))


def approximate_poa_wm2(ghi_wm2: float, incidence_cos: float, sun_elev_deg: float) -> float:
    """
    Prosta aproksymacja POA z GHI (bez full pvlib).

    Przy niskim słońcu GHI jest małe względem energii na panelach południowych
    — mnożnik cos(incidence)/sin(elevation) tłumi rano/wieczór przy złym kącie.
    """
    if ghi_wm2 is None or (isinstance(ghi_wm2, float) and np.isnan(ghi_wm2)):
        return 0.0
    ghi = max(0.0, float(ghi_wm2))
    if sun_elev_deg <= 1.0 or incidence_cos <= 0:
        return 0.0
    # Skala: przy południu (wysokie elev, dobry kąt) ≈ GHI; rano przy dużym θ — niżej
    scale = incidence_cos / max(np.sin(np.radians(sun_elev_deg)), 0.05)
    scale = float(np.clip(scale, 0.0, 1.5))
    return ghi * scale


def add_panel_geometry_features(
    df: pd.DataFrame,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    tilt_deg: float | None = None,
    azimuth_deg: float | None = None,
) -> pd.DataFrame:
    """
    Dodaj cechy geometrii paneli do ramki z kolumnami day, hour [, radiation_wm2].

    Nie zmienia modelu produkcyjnego — tylko kolumny w DataFrame.
    """
    if 'day' not in df.columns or 'hour' not in df.columns:
        raise ValueError('Wymagane kolumny: day, hour')

    lat = latitude if latitude is not None else float(os.getenv('WEATHER_LAT', '50.06'))
    lon = longitude if longitude is not None else float(os.getenv('WEATHER_LON', '19.94'))
    if tilt_deg is None or azimuth_deg is None:
        t_default, a_default = get_panel_params()
        tilt_deg = tilt_deg if tilt_deg is not None else t_default
        azimuth_deg = azimuth_deg if azimuth_deg is not None else a_default

    out = df.copy()
    cache: dict[tuple[str, int], tuple[float, float]] = {}

    elevs: list[float] = []
    azs: list[float] = []
    cos_i: list[float] = []

    for day, hour in zip(out['day'].astype(str), out['hour'].astype(int)):
        key = (day, hour)
        if key not in cache:
            cache[key] = _solar_angles_for_hour(day, hour, lat, lon)
        elev, az = cache[key]
        elevs.append(elev)
        azs.append(az)
        cos_i.append(incidence_cosine(elev, az, tilt_deg, azimuth_deg))

    out['sun_elevation_deg'] = elevs
    out['sun_azimuth_deg'] = azs
    out['incidence_cos'] = cos_i

    if 'radiation_wm2' in out.columns:
        out['poa_approx_wm2'] = [
            approximate_poa_wm2(g, c, e)
            for g, c, e in zip(out['radiation_wm2'], out['incidence_cos'], out['sun_elevation_deg'])
        ]
    else:
        out['poa_approx_wm2'] = 0.0

    return out
