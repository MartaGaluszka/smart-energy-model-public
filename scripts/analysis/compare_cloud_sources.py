#!/usr/bin/env python
"""
Porównanie zachmurzenia / nasłonecznienia: Open-Meteo (modele) vs IMGW.

Dla dni z dużym błędem PV (domyślnie 2026-07-09, 2026-07-12):
  1) Open-Meteo archive — kilka modeli + stary vs nowy GPS
  2) IMGW synop (Kraków-Balice) — usłonecznienie USL [h] gdy miesiąc opublikowany
  3) Produkcja FoxESS (app / pvPower) jako „prawda o dniu”

Uwaga: IMGW dobowe synop za lipiec 2026 pojawia się zwykle z opóźnieniem
(na 2026-07-17 dostępne do czerwca). Wtedy raportuje tylko Open-Meteo + PV.

Uruchomienie:
    PYTHONPATH=$PWD python scripts/compare_cloud_sources.py
    PYTHONPATH=$PWD python scripts/compare_cloud_sources.py --days 2026-07-09,2026-07-12
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import urllib.parse
import urllib.request
import zipfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv()

import numpy as np
import pandas as pd
import sqlite3

from src.data.foxess_pv_total import resolve_actual_pv_total
from src.models.forecast_validation import get_actual_pv_ml

OLD_LAT, OLD_LON = 50.0647, 19.9450
IMGW_SYNOP_BASE = (
    'https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/'
    'dane_meteorologiczne/dobowe/synop'
)
# s_d_*.csv — USL = usłonecznienie [h] (indeks 20)
USL_IDX = 20
STATION_PREF = ('KRAKÓW-BALICE', 'KRAKOW-BALICE', 'BALICE')


def _http_json(url: str, timeout: int = 120) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _http_bytes(url: str, timeout: int = 120) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()


def fetch_om_hourly(
    lat: float,
    lon: float,
    start: str,
    end: str,
    model: str | None = None,
) -> pd.DataFrame:
    params = {
        'latitude': lat,
        'longitude': lon,
        'start_date': start,
        'end_date': end,
        'hourly': 'cloud_cover,cloud_cover_low,shortwave_radiation,sunshine_duration',
        'timezone': 'Europe/Warsaw',
    }
    if model:
        params['models'] = model
    url = 'https://archive-api.open-meteo.com/v1/archive?' + urllib.parse.urlencode(params)
    payload = _http_json(url)
    if payload.get('error'):
        raise RuntimeError(payload.get('reason') or payload)
    h = payload['hourly']
    df = pd.DataFrame(h)
    df['timestamp'] = pd.to_datetime(df['time'])
    df['day'] = df['timestamp'].dt.strftime('%Y-%m-%d')
    df['hour'] = df['timestamp'].dt.hour
    return df


def summarize_day(df: pd.DataFrame, day: str, daylight: tuple[int, int] = (5, 20)) -> dict:
    sub = df[(df['day'] == day) & (df['hour'] >= daylight[0]) & (df['hour'] <= daylight[1])]
    if sub.empty:
        return {}
    cloud = sub['cloud_cover'].astype(float)
    rad = sub['shortwave_radiation'].astype(float)
    sun = sub['sunshine_duration'].astype(float) if 'sunshine_duration' in sub else None
    return {
        'cloud_avg': float(cloud.mean()),
        'cloud_max': float(cloud.max()),
        'hours_cloud_ge70': int((cloud >= 70).sum()),
        'hours_cloud_ge90': int((cloud >= 90).sum()),
        'rad_mean': float(rad.mean()),
        'rad_sum_kwh_m2': float(rad.sum() / 1000.0),
        'sunshine_h': float(sun.sum() / 3600.0) if sun is not None else float('nan'),
    }


def load_db_om(days: list[str], db_path: str, location: str = 'home') -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    q = f'''
        SELECT timestamp, cloud_cover_percent, cloud_cover_low_percent,
               solar_radiation_wm2, sunshine_duration_min, data_source
        FROM weather_data
        WHERE location = ? AND data_source = 'OpenMeteo-archive'
          AND date(timestamp) IN ({','.join('?' * len(days))})
        ORDER BY timestamp
    '''
    df = pd.read_sql_query(q, conn, params=[location, *days])
    conn.close()
    if df.empty:
        return df
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['day'] = df['timestamp'].dt.strftime('%Y-%m-%d')
    df['hour'] = df['timestamp'].dt.hour
    df = df.rename(columns={
        'cloud_cover_percent': 'cloud_cover',
        'shortwave_radiation': 'shortwave_radiation',
        'solar_radiation_wm2': 'shortwave_radiation',
    })
    # sunshine in DB is minutes → seconds-compatible helper uses sunshine_duration
    df['sunshine_duration'] = df['sunshine_duration_min'].fillna(0) * 60.0
    return df


def fetch_imgw_usl(year: int, month: int, station_name: str = 'KRAKÓW-BALICE') -> pd.DataFrame:
    """Usłonecznienie dobowe IMGW (proxy zachmurzenia) z s_d_MM_YYYY.csv."""
    url = f'{IMGW_SYNOP_BASE}/{year}/{year}_{month:02d}_s.zip'
    try:
        raw = _http_bytes(url)
    except Exception as exc:
        raise FileNotFoundError(f'Brak archiwum IMGW {url}: {exc}') from exc

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = zf.namelist()
        csv_name = next((n for n in names if n.startswith('s_d_') and n.endswith('.csv')), None)
        if not csv_name:
            raise FileNotFoundError(f'Brak s_d_*.csv w {url}: {names}')
        text = zf.read(csv_name).decode('cp1250')

    rows = []
    for line in text.splitlines():
        parts = next(csv.reader([line]))
        if len(parts) <= USL_IDX:
            continue
        name = parts[1].strip()
        if name.upper().replace('Ó', 'O') != station_name.upper().replace('Ó', 'O'):
            if not any(name.upper().startswith(p.replace('Ó', 'O')) for p in STATION_PREF):
                continue
        try:
            y, m, d = int(parts[2]), int(parts[3]), int(parts[4])
            usl = float(parts[USL_IDX]) if parts[USL_IDX] not in ('', None) else float('nan')
        except (ValueError, TypeError):
            continue
        rows.append({
            'day': f'{y:04d}-{m:02d}-{d:02d}',
            'station': name,
            'imgw_sunshine_h': usl,
            'imgw_precip_mm': pd.to_numeric(parts[13], errors='coerce'),
            'imgw_temp_mean': pd.to_numeric(parts[9], errors='coerce'),
        })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description='Porównanie źródeł zachmurzenia OM vs IMGW')
    parser.add_argument(
        '--days',
        default='2026-07-09,2026-07-12',
        help='Lista dni YYYY-MM-DD po przecinku',
    )
    parser.add_argument(
        '--out',
        default='data/processed/cloud_source_comparison.csv',
        help='CSV z wynikami dziennymi',
    )
    args = parser.parse_args()
    days = [d.strip() for d in args.days.split(',') if d.strip()]
    start, end = min(days), max(days)

    lat = float(os.getenv('WEATHER_LAT', '50.06'))
    lon = float(os.getenv('WEATHER_LON', '19.94'))
    db = os.getenv('DATABASE_PATH', 'data/energy_model.db')

    print('=' * 72)
    print('PORÓWNANIE ŹRÓDEŁ ZACHMURZENIA / NASŁONECZNIENIA')
    print(f'Dni: {", ".join(days)}')
    print(f'GPS dach: {lat}, {lon}  |  stary GPS: {OLD_LAT}, {OLD_LON}')
    print('=' * 72)

    models = [
        ('best_match', None),
        ('ecmwf_ifs025', 'ecmwf_ifs025'),
        ('icon_seamless', 'icon_seamless'),
        ('icon_eu', 'icon_eu'),
        ('era5_seamless', 'era5_seamless'),
    ]

    print('\n[1] Open-Meteo archive — modele (GPS dach, godz. 5–20)...')
    model_frames: dict[str, pd.DataFrame] = {}
    for label, model in models:
        try:
            model_frames[label] = fetch_om_hourly(lat, lon, start, end, model)
            print(f'  ✓ {label}')
        except Exception as exc:
            print(f'  ✗ {label}: {exc}')

    print('\n[2] Open-Meteo — stary GPS (best_match)...')
    try:
        old_gps = fetch_om_hourly(OLD_LAT, OLD_LON, start, end, None)
        print('  ✓ stary GPS')
    except Exception as exc:
        old_gps = pd.DataFrame()
        print(f'  ✗ {exc}')

    print('\n[3] Pogoda z bazy (po refetch dach)...')
    db_om = load_db_om(days, db)
    print(f'  rekordów: {len(db_om)}')

    print('\n[4] IMGW synop Kraków-Balice (usłonecznienie USL)...')
    imgw_by_month: dict[tuple[int, int], pd.DataFrame] = {}
    for day in days:
        y, m = int(day[:4]), int(day[5:7])
        key = (y, m)
        if key in imgw_by_month:
            continue
        try:
            imgw_by_month[key] = fetch_imgw_usl(y, m)
            print(f'  ✓ {y}-{m:02d}: {len(imgw_by_month[key])} dni Balice')
        except Exception as exc:
            imgw_by_month[key] = pd.DataFrame()
            print(f'  ✗ {y}-{m:02d}: {exc}')

    # dystans Balice
    print(f'  (Balice ≈ lotnisko KRK — ~11–15 km od dachu; Libertów bliżej, ale bez synop USL w s_d)')

    rows = []
    print('\n' + '=' * 72)
    print('WYNIKI PER DZIEŃ')
    print('=' * 72)

    for day in days:
        print(f'\n### {day}')
        app, src = resolve_actual_pv_total(day, db)
        pv_ml = get_actual_pv_ml(day, db)
        print(f'  FoxESS app (PVEnergyTotal): {app} kWh ({src})')
        print(f'  Suma pvPower (ML):          {pv_ml:.2f} kWh' if pv_ml is not None else '  pvPower: brak')

        day_row = {'day': day, 'pv_app_kwh': app, 'pv_ml_kwh': pv_ml}

        print('\n  Open-Meteo cloud_avg % / rad_sum kWh/m² / sunshine_h (5–20h):')
        print(f'  {"model":16s} {"cloud":>7s} {"h≥70":>5s} {"h≥90":>5s} {"radΣ":>7s} {"sun_h":>6s}')
        for label in model_frames:
            s = summarize_day(model_frames[label], day)
            if not s:
                continue
            print(
                f'  {label:16s} {s["cloud_avg"]:7.1f} {s["hours_cloud_ge70"]:5d} '
                f'{s["hours_cloud_ge90"]:5d} {s["rad_sum_kwh_m2"]:7.2f} {s["sunshine_h"]:6.2f}'
            )
            day_row[f'om_{label}_cloud'] = s['cloud_avg']
            day_row[f'om_{label}_rad'] = s['rad_sum_kwh_m2']
            day_row[f'om_{label}_sun_h'] = s['sunshine_h']

        if not db_om.empty:
            s = summarize_day(db_om.rename(columns={'cloud_cover': 'cloud_cover'}), day)
            # db uses same colnames after load_db_om
            sub = db_om[(db_om['day'] == day) & (db_om['hour'] >= 5) & (db_om['hour'] <= 20)]
            if not sub.empty:
                s = {
                    'cloud_avg': float(sub['cloud_cover'].mean()),
                    'hours_cloud_ge70': int((sub['cloud_cover'] >= 70).sum()),
                    'hours_cloud_ge90': int((sub['cloud_cover'] >= 90).sum()),
                    'rad_sum_kwh_m2': float(sub['shortwave_radiation'].sum() / 1000.0),
                    'sunshine_h': float(sub['sunshine_duration'].sum() / 3600.0),
                }
                print(
                    f'  {"db_refetch":16s} {s["cloud_avg"]:7.1f} {s["hours_cloud_ge70"]:5d} '
                    f'{s["hours_cloud_ge90"]:5d} {s["rad_sum_kwh_m2"]:7.2f} {s["sunshine_h"]:6.2f}'
                )
                day_row['om_db_cloud'] = s['cloud_avg']
                day_row['om_db_rad'] = s['rad_sum_kwh_m2']

        if not old_gps.empty:
            s = summarize_day(old_gps, day)
            if s:
                print(
                    f'  {"old_GPS":16s} {s["cloud_avg"]:7.1f} {s["hours_cloud_ge70"]:5d} '
                    f'{s["hours_cloud_ge90"]:5d} {s["rad_sum_kwh_m2"]:7.2f} {s["sunshine_h"]:6.2f}'
                )
                day_row['om_oldgps_cloud'] = s['cloud_avg']
                day_row['om_oldgps_rad'] = s['rad_sum_kwh_m2']

        y, m = int(day[:4]), int(day[5:7])
        imgw = imgw_by_month.get((y, m), pd.DataFrame())
        if not imgw.empty and day in set(imgw['day']):
            r = imgw[imgw['day'] == day].iloc[0]
            print(
                f'\n  IMGW {r["station"]}: usłonecznienie={r["imgw_sunshine_h"]:.1f} h, '
                f'opad={r["imgw_precip_mm"]}, Tśr={r["imgw_temp_mean"]}'
            )
            day_row['imgw_sunshine_h'] = r['imgw_sunshine_h']
            day_row['imgw_precip_mm'] = r['imgw_precip_mm']
        else:
            print('\n  IMGW: brak danych za ten miesiąc (archiwum jeszcze nieopublikowane)')
            day_row['imgw_sunshine_h'] = np.nan

        # Interpretacja
        bm = day_row.get('om_best_match_cloud')
        icon = day_row.get('om_icon_seamless_cloud')
        if bm is not None and icon is not None:
            delta = icon - bm
            print(f'\n  Δ cloud ICON−best_match: {delta:+.1f} pp', end='')
            if delta > 15:
                print('  → best_match może być ZA SŁONECZNY względem ICON')
            elif delta < -15:
                print('  → ICON jaśniejszy niż best_match')
            else:
                print('  → modele zbliżone')

        rows.append(day_row)

    out = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    out.to_csv(args.out, index=False)
    print(f'\n✓ Zapisano: {args.out}')

    print('\n' + '=' * 72)
    print('WNIOSKI')
    print('=' * 72)
    print('''
• Jeśli ICON/ERA5 mają wyraźnie więcej chmur niż best_match przy niskim PV
  → Open-Meteo „gładzi” dzień; rozważ model icon_seamless w fetch_weather
  albo silniejszą korektę FORECAST_CLOUDY_* / intraday.

• IMGW USL (Balice): mało godzin słońca = potwierdzenie pochmurnego dnia.
  Brak lipca w archiwum = poczekaj na publikację 2026_07_s.zip (~pocz. VIII).

• Stary vs nowy GPS: różnica cloud/rad pokazuje wpływ przesunięcia komórki.
''')


if __name__ == '__main__':
    main()
