"""
Pobiera dobowe dane IMGW (klimat): pokrywa śnieżna, opady, temperatura.

Wymaga w .env: WEATHER_LAT, WEATHER_LON (współrzędne instalacji PV).
Opcjonalnie: IMGW_STATION_CODE — wymuszenie stacji (np. 250190390).

Uruchomienie:
    python scripts/fetch_imgw_snow.py
    python scripts/fetch_imgw_snow.py --start 2025-09-01 --end 2026-02-28
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

from src.data.household_context import ML_BATTERY_START
from src.data.imgw_api import fetch_climate_daily, save_imgw_daily_to_db
from src.data.weather_api import OpenMeteoClient, load_daily_pv_daytime

load_dotenv()

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')
DEFAULT_START = os.getenv('IMGW_START_DATE', ML_BATTERY_START.isoformat())
DEFAULT_END = os.getenv('IMGW_END_DATE', '2026-02-28')
STATION_OVERRIDE = os.getenv('IMGW_STATION_CODE')


def _snow_label(cm) -> str:
    if cm is None or (isinstance(cm, float) and cm != cm):
        return 'brak pomiaru / brak zjawiska (status 8/9)'
    return f'{cm:.0f} cm'


def main() -> None:
    parser = argparse.ArgumentParser(description='IMGW klimat → imgw_daily (śnieg)')
    parser.add_argument('--start', default=DEFAULT_START)
    parser.add_argument('--end', default=DEFAULT_END)
    args = parser.parse_args()

    client = OpenMeteoClient.from_env()
    df, station = fetch_climate_daily(
        client.latitude,
        client.longitude,
        args.start,
        args.end,
        station_code=STATION_OVERRIDE,
    )

    print('=' * 72)
    print('IMGW klimat → imgw_daily (pokrywa śnieżna)')
    print(f'Instalacja: ({client.latitude}, {client.longitude})')
    print(
        f'Stacja: {station["station_name"]} [{station["station_code"]}] '
        f'~{station["distance_km"]:.1f} km'
    )
    print(f'Okres: {args.start} – {args.end}')
    print('=' * 72)

    if df.empty:
        print('❌ Brak danych IMGW w podanym okresie.')
        sys.exit(1)

    n = save_imgw_daily_to_db(df, station, DB_PATH)
    print(f'✅ Zapisano {n} dni do imgw_daily')

    snow_days = df[df['snow_depth_cm'].notna() & (df['snow_depth_cm'] > 0)]
    print(f'   Dni ze śniegiem (pokrywa > 0): {len(snow_days)}')

    check_days = ['2025-12-13', '2025-12-14', '2025-12-15', '2025-12-31']
    pv = load_daily_pv_daytime(DB_PATH, args.start, args.end)
    print('\nWalidacja wybranych dni (IMGW + PV 9–16h):')
    for d in check_days:
        if d < args.start or d > args.end:
            continue
        row = df[df['day'] == d]
        pv_row = pv[pv['day'] == d]
        if row.empty:
            continue
        r = row.iloc[0]
        pv916 = float(pv_row.iloc[0]['pv_kwh_daytime']) if not pv_row.empty else None
        pv_txt = f'{pv916:.1f} kWh' if pv916 is not None else '—'
        print(
            f'  {d}: śnieg IMGW={_snow_label(r["snow_depth_cm"])}, '
            f'opady={r["precip_mm"] if r["precip_mm"] == r["precip_mm"] else "—"} mm, '
            f'T={r["temp_mean_c"]}°C, PV 9–16h={pv_txt}'
        )

    print('\n💡 Uwaga: brak śniegu w IMGW nie wyklucza lokalnej pokrywy na panelach (dach vs stacja).')
    print('   Do prognozy 1–2 dni używaj snow_depth/snowfall z Open-Meteo (fetch_weather.py).')


if __name__ == '__main__':
    main()
