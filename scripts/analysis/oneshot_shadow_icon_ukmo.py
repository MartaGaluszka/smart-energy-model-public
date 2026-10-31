#!/usr/bin/env python
"""
Oneshot shadow: RF16 / CS4 x pogoda ICON / UKMO (forecast lub archive).

Zapisuje data/processed/oneshot_shadow_icon_ukmo_YYYYMMDD_HHMM.csv (gitignored)
oraz statystyki nieba (6-20) i liczbe godzin z brakiem radiacji (UKMO NaN).

Uruchomienie:
    PYTHONPATH=$PWD python scripts/analysis/oneshot_shadow_icon_ukmo.py --days 3
    PYTHONPATH=$PWD python scripts/analysis/oneshot_shadow_icon_ukmo.py --start 2026-10-18 --days 3 --archive
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')

from scripts.analysis.oneshot_rf_icon_vs_ukmo import (  # noqa: E402
    _api_to_hourly,
    features_from_weather,
    predict_daily,
)
from src.data.foxess_pv_total import resolve_actual_pv_total  # noqa: E402
from src.data.weather_api import OpenMeteoClient  # noqa: E402
from src.features.clearness import add_clearness_features  # noqa: E402
from src.models.pv_hourly_predictor import PVHourlyPredictor  # noqa: E402

MODELS = {
    'RF': ROOT / 'models/pv_hourly_model.joblib',
    'CS4': ROOT / 'models/pv_hourly_model_cs4.joblib',
}
WEATHER = {'I': 'icon_seamless', 'U': 'ukmo_seamless'}


def _merge_cloud_layers(
    feats: pd.DataFrame, raw: pd.DataFrame, *, lat: float, lon: float,
) -> pd.DataFrame:
    layers = raw.copy()
    layers['timestamp'] = pd.to_datetime(layers['timestamp'])
    layers['day'] = layers['timestamp'].dt.strftime('%Y-%m-%d')
    layers['hour'] = layers['timestamp'].dt.hour
    layers = layers.rename(columns={
        'cloud_cover_low_percent': 'cloud_cover_low_pct',
        'cloud_cover_mid_percent': 'cloud_cover_mid_pct',
    })
    keep = [c for c in ('day', 'hour', 'cloud_cover_low_pct', 'cloud_cover_mid_pct') if c in layers.columns]
    feats = feats.merge(
        layers[keep].drop_duplicates(['day', 'hour'], keep='last'),
        on=['day', 'hour'],
        how='left',
    )
    for c in ('cloud_cover_low_pct', 'cloud_cover_mid_pct'):
        if c not in feats.columns:
            feats[c] = feats['cloud_cover_pct']
        feats[c] = feats[c].fillna(feats['cloud_cover_pct'])
    return add_clearness_features(feats, latitude=lat, longitude=lon)


def _fetch_weather(
    wm: str,
    days: list[str],
    *,
    use_archive: bool,
    forecast_days: int,
    lat: float,
    lon: float,
) -> pd.DataFrame:
    client = OpenMeteoClient(lat, lon, model=wm)
    today = date.today()
    want = {date.fromisoformat(d) for d in days}
    past = sorted(d for d in want if d <= today)
    future = sorted(d for d in want if d > today)

    parts: list[pd.DataFrame] = []
    if use_archive and past:
        parts.append(client.fetch_archive(past[0].isoformat(), past[-1].isoformat()))
    if future or not use_archive:
        parts.append(client.fetch_forecast(forecast_days=forecast_days))
    if not parts:
        return pd.DataFrame()

    raw = pd.concat(parts, ignore_index=True)
    if 'timestamp' in raw.columns:
        raw['timestamp'] = pd.to_datetime(raw['timestamp'])
        raw = raw.sort_values('timestamp').drop_duplicates(subset=['timestamp'], keep='last')
    return raw


def run_oneshot(
    days: list[str],
    *,
    use_archive: bool,
    lat: float,
    lon: float,
    db: str,
    predictors: dict[str, PVHourlyPredictor],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = {d: {'day': d} for d in days}
    sky_rows = []
    forecast_days = max(3, (date.fromisoformat(days[-1]) - date.today()).days + 2)

    for wk, wm in WEATHER.items():
        raw = _fetch_weather(
            wm, days, use_archive=use_archive, forecast_days=forecast_days, lat=lat, lon=lon,
        )
        weather = _api_to_hourly(raw)
        w = weather[weather['day'].isin(days)]
        day_w = w[(w['hour'] >= 6) & (w['hour'] <= 20)]
        for d in days:
            dd = day_w[day_w['day'] == d]
            sky_rows.append({
                'day': d,
                'wx': wk,
                'cloud_pct': dd['cloud_cover_pct'].mean(),
                'precip_mm': dd['precip_mm'].sum(),
                'rad_wh': dd['radiation_wm2'].sum(),
                'rad_nan_h': int(dd['radiation_wm2'].isna().sum()),
                'hours': len(dd),
            })
        feats = features_from_weather(weather, days, lat, lon)
        feats = _merge_cloud_layers(feats, raw, lat=lat, lon=lon)
        for mname, pr in predictors.items():
            daily = predict_daily(pr, feats).set_index('day')['predicted_kwh']
            for d in days:
                val = daily.get(d, np.nan)
                rows[d][f'{mname}_{wk}'] = float(val) if pd.notna(val) else np.nan

    out = pd.DataFrame(rows.values())
    out['RF_half'] = (out['RF_I'] + out['RF_U']) / 2
    out['CS4_half'] = (out['CS4_I'] + out['CS4_U']) / 2
    apps = [resolve_actual_pv_total(d, db) for d in days]
    out['app_kwh'] = [a[0] for a in apps]
    out['app_src'] = [a[1] for a in apps]
    sky = pd.DataFrame(sky_rows)
    return out, sky


def main() -> None:
    p = argparse.ArgumentParser(description='Oneshot shadow ICON/UKMO x RF/CS4')
    p.add_argument('--days', type=int, default=3, help='liczba dni od startu')
    p.add_argument('--start', default=None, help='pierwszy dzien YYYY-MM-DD (domyslnie dzis)')
    p.add_argument(
        '--archive',
        action='store_true',
        help='Open-Meteo archive (dni historyczne / retro notatki)',
    )
    p.add_argument(
        '--stamp',
        default=None,
        help='np. 20261018_archive — nazwa pliku zamiast now',
    )
    args = p.parse_args()

    today = date.today()
    if args.start:
        d0 = date.fromisoformat(args.start)
    else:
        d0 = today
    days = [(d0 + timedelta(days=i)).isoformat() for i in range(args.days)]

    use_archive = args.archive
    if not use_archive and all(date.fromisoformat(d) < today for d in days):
        use_archive = True

    lat = float(os.getenv('WEATHER_LAT', '50.06'))
    lon = float(os.getenv('WEATHER_LON', '19.94'))
    db = os.getenv('DATABASE_PATH', str(ROOT / 'data/energy_model.db'))
    if not Path(db).is_absolute():
        db = str(ROOT / db)

    predictors = {}
    for name, path in MODELS.items():
        pr = PVHourlyPredictor(str(path))
        pr.load()
        predictors[name] = pr

    out, sky = run_oneshot(
        days, use_archive=use_archive, lat=lat, lon=lon, db=db, predictors=predictors,
    )

    if args.stamp:
        stamp = args.stamp
    else:
        stamp = datetime.now().strftime('%Y%m%d_%H%M')
        if use_archive and args.start:
            stamp = f"{args.start.replace('-', '')}_archive"

    path = ROOT / f'data/processed/oneshot_shadow_icon_ukmo_{stamp}.csv'
    out.to_csv(path, index=False)
    sky.to_csv(ROOT / f'data/processed/oneshot_shadow_icon_ukmo_{stamp}_sky.csv', index=False)

    pd.set_option('display.width', 200)
    mode = 'archive' if use_archive else 'forecast'
    print(f'mode={mode} days={days[0]}..{days[-1]}')
    print(out.round(2).to_string(index=False))
    print()
    print(sky.round(1).to_string(index=False))
    print(f'\n✓ {path.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
