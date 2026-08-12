#!/usr/bin/env python
"""
Oneshot (bez produkcji): Open-Meteo ICON vs UKMO — opad/chmury na GPS dachu.

Nie zmienia .env / weather_data / .joblib.

Uruchomienie:
    PYTHONPATH=$PWD python scripts/analysis/oneshot_icon_vs_ukmo_precip.py
    PYTHONPATH=$PWD python scripts/analysis/oneshot_icon_vs_ukmo_precip.py --start 2026-07-21 --end 2026-07-24
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')

OUT = ROOT / 'data/processed/oneshot_icon_vs_ukmo_precip.csv'


def fetch_hourly(lat: float, lon: float, start: str, end: str, model: str) -> pd.DataFrame:
    params = {
        'latitude': lat,
        'longitude': lon,
        'start_date': start,
        'end_date': end,
        'hourly': 'precipitation,cloud_cover,cloud_cover_low,shortwave_radiation',
        'timezone': 'Europe/Warsaw',
        'models': model,
    }
    url = 'https://archive-api.open-meteo.com/v1/archive?' + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as resp:
        payload = json.loads(resp.read().decode())
    if payload.get('error'):
        raise RuntimeError(f'{model}: {payload.get("reason")}')
    h = payload['hourly']
    df = pd.DataFrame(h)
    df['timestamp'] = pd.to_datetime(df['time'])
    df['day'] = df['timestamp'].dt.strftime('%Y-%m-%d')
    df['hour'] = df['timestamp'].dt.hour
    df['model'] = model
    return df


def day_summary(df: pd.DataFrame, day: str, lo: int = 5, hi: int = 20) -> dict:
    sub = df[(df['day'] == day) & (df['hour'] >= lo) & (df['hour'] <= hi)]
    if sub.empty:
        return {}
    precip = sub['precipitation'].astype(float)
    cloud = sub['cloud_cover'].astype(float)
    # first hour with precip >= 0.2 mm in daylight
    wet = sub[precip >= 0.2]
    first_wet = int(wet['hour'].iloc[0]) if not wet.empty else None
    morning = sub[sub['hour'].between(6, 11)]
    midday = sub[sub['hour'].between(12, 15)]
    return {
        'precip_sum_mm': float(precip.sum()),
        'precip_morning_6_11': float(morning['precipitation'].astype(float).sum()),
        'precip_midday_12_15': float(midday['precipitation'].astype(float).sum()),
        'first_wet_hour_ge0.2': first_wet,
        'cloud_avg': float(cloud.mean()),
        'rad_sum': float(sub['shortwave_radiation'].astype(float).sum()),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--start', default='2026-07-21')
    p.add_argument('--end', default='2026-07-24')
    p.add_argument('--out', default=str(OUT))
    args = p.parse_args()

    lat = float(os.getenv('WEATHER_LAT', '50.06'))
    lon = float(os.getenv('WEATHER_LON', '19.94'))

    print('=' * 72)
    print('ONESHOT: ICON vs UKMO (Open-Meteo archive) — bez produkcji')
    print(f'GPS {lat}, {lon}  |  {args.start} → {args.end}')
    print('=' * 72)

    frames = {}
    for model in ('icon_seamless', 'ukmo_seamless'):
        print(f'\n[fetch] {model}...')
        frames[model] = fetch_hourly(lat, lon, args.start, args.end, model)
        print(f'  {len(frames[model])} h')

    days = sorted(frames['icon_seamless']['day'].unique())
    rows = []
    print('\n' + '=' * 72)
    print(f'{"dzień":12s} {"model":16s} {"Σmm":>6s} {"6–11":>6s} {"12–15":>6s} {"1.wet":>6s} {"cloud":>6s}')
    for day in days:
        for model, df in frames.items():
            s = day_summary(df, day)
            if not s:
                continue
            print(
                f'{day:12s} {model:16s} {s["precip_sum_mm"]:6.1f} '
                f'{s["precip_morning_6_11"]:6.1f} {s["precip_midday_12_15"]:6.1f} '
                f'{str(s["first_wet_hour_ge0.2"] or "—"):>6s} {s["cloud_avg"]:6.0f}'
            )
            rows.append({'day': day, 'model': model, **s})

    out = pd.DataFrame(rows)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)

    # hourly side-by-side for latest day (today-ish)
    last = days[-1]
    a = frames['icon_seamless']
    b = frames['ukmo_seamless']
    m = a.merge(
        b[['timestamp', 'precipitation', 'cloud_cover']],
        on='timestamp',
        suffixes=('_icon', '_ukmo'),
    )
    hourly_out = ROOT / 'data/processed' / f'oneshot_icon_vs_ukmo_hourly_{last.replace("-", "")}.csv'
    m[m['day'] == last].to_csv(hourly_out, index=False)

    print(f'\n✓ {args.out}')
    print(f'✓ {hourly_out}')
    print('\nWerdykt oneshot: porównuj first_wet_hour i precip_morning vs Twoja obserwacja.')
    print('Nie zmieniaj OPENMETEO_MODEL=icon_seamless bez gate / decyzji T2.')


if __name__ == '__main__':
    main()
