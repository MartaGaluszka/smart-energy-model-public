#!/usr/bin/env python
"""
Podgląd cech geometrii paneli (tilt/azymut) — bez zmiany modelu produkcyjnego.

Użycie:
    python scripts/preview_panel_geometry.py
    python scripts/preview_panel_geometry.py --day 2026-07-17
    python scripts/preview_panel_geometry.py --day 2026-07-17 --tilt 35 --azimuth 180
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv()

import pandas as pd

from src.features.panel_geometry import (
    PANEL_GEOMETRY_COLUMNS,
    add_panel_geometry_features,
    get_panel_params,
)
from src.models.forecast_archive import ARCHIVE_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description='Podgląd geometrii paneli (tilt/azymut)')
    parser.add_argument('--day', default=None, help='YYYY-MM-DD (domyślnie dziś)')
    parser.add_argument('--tilt', type=float, default=None, help='Nachylenie [°]')
    parser.add_argument('--azimuth', type=float, default=None, help='Azymut [°], 180=S')
    parser.add_argument(
        '--forecast',
        default=None,
        help='CSV prognozy (opcjonalnie) — użyje radiation/cloud z archiwum',
    )
    args = parser.parse_args()

    from datetime import date

    day = args.day or date.today().isoformat()
    tilt, az = get_panel_params()
    if args.tilt is not None:
        tilt = args.tilt
    if args.azimuth is not None:
        az = args.azimuth

    lat = float(os.getenv('WEATHER_LAT', '50.06'))
    lon = float(os.getenv('WEATHER_LON', '19.94'))

    # Baza godzin z prognozy lub siatka 5–20
    frame = None
    if args.forecast and os.path.exists(args.forecast):
        frame = pd.read_csv(args.forecast)
        frame = frame[frame['day'] == day].copy()
    else:
        # Najnowszy daily forecast dla dnia, jeśli jest
        import glob

        candidates = sorted(glob.glob(os.path.join(ARCHIVE_DIR, f'pv_forecast_{day.replace("-", "")}_*.csv')))
        # also yesterday archives that include today
        if not candidates:
            candidates = sorted(glob.glob(os.path.join(ARCHIVE_DIR, 'pv_forecast_*.csv')))
        for path in reversed(candidates):
            df = pd.read_csv(path)
            if 'day' in df.columns and (df['day'] == day).any():
                frame = df[df['day'] == day].copy()
                print(f'Źródło radiacji: {path}')
                break

    if frame is None or frame.empty:
        frame = pd.DataFrame({
            'day': [day] * 16,
            'hour': list(range(5, 21)),
            'radiation_wm2': [0.0] * 16,
        })
        print('⚠️ Brak archiwum — tylko kąty słońca (bez POA z GHI)')

    out = add_panel_geometry_features(
        frame,
        latitude=lat,
        longitude=lon,
        tilt_deg=tilt,
        azimuth_deg=az,
    )

    cols = ['hour']
    if 'radiation_wm2' in out.columns:
        cols.append('radiation_wm2')
    if 'cloud_cover_pct' in out.columns:
        cols.append('cloud_cover_pct')
    if 'predicted_kwh' in out.columns:
        cols.append('predicted_kwh')
    cols += PANEL_GEOMETRY_COLUMNS

    print('=' * 72)
    print(f'GEOMETRIA PANELI — {day}')
    print(f'tilt={tilt:.0f}°  azymut={az:.0f}° (180=S)  lat={lat} lon={lon}')
    print('=' * 72)
    show = out[cols].copy()
    for c in PANEL_GEOMETRY_COLUMNS + ['radiation_wm2', 'predicted_kwh']:
        if c in show.columns:
            show[c] = show[c].round(2)
    print(show.to_string(index=False))

    morning = out[out['hour'].between(5, 9)]
    midday = out[out['hour'].between(11, 14)]
    print('\n--- Średnie ---')
    print(
        f"Rano 5–9h:  incidence_cos={morning['incidence_cos'].mean():.2f}  "
        f"elev={morning['sun_elevation_deg'].mean():.1f}°  "
        f"poa≈{morning['poa_approx_wm2'].mean():.0f} W/m²"
    )
    print(
        f"Południe 11–14h: incidence_cos={midday['incidence_cos'].mean():.2f}  "
        f"elev={midday['sun_elevation_deg'].mean():.1f}°  "
        f"poa≈{midday['poa_approx_wm2'].mean():.0f} W/m²"
    )
    print(
        '\nℹ️  Model produkcyjny NIE używa tych cech '
        '(PANEL_GEOMETRY_FEATURES=0). Po tygodniu: włącz → porównaj → ACCEPT/REJECT.'
    )


if __name__ == '__main__':
    main()
