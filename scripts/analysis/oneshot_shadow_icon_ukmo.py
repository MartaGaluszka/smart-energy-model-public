#!/usr/bin/env python
"""
Oneshot shadow: RF16 / CS4 x pogoda ICON / UKMO z forecast API (bez zapisu do DB).

Zapisuje data/processed/oneshot_shadow_icon_ukmo_YYYYMMDD_HHMM.csv (gitignored)
oraz statystyki nieba (6-20) i liczbe godzin z brakiem radiacji (UKMO NaN).

Uruchomienie:
    PYTHONPATH=$PWD python scripts/analysis/oneshot_shadow_icon_ukmo.py --days 3
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


def main() -> None:
    p = argparse.ArgumentParser(description='Oneshot shadow ICON/UKMO x RF/CS4')
    p.add_argument('--days', type=int, default=3, help='liczba dni od dzis')
    args = p.parse_args()

    today = date.today()
    days = [(today + timedelta(days=i)).isoformat() for i in range(args.days)]
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

    rows = {d: {'day': d} for d in days}
    sky_rows = []
    for wk, wm in WEATHER.items():
        raw = OpenMeteoClient(lat, lon, model=wm).fetch_forecast(forecast_days=args.days + 1)
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
        layers = raw.copy()
        layers['timestamp'] = pd.to_datetime(layers['timestamp'])
        layers['day'] = layers['timestamp'].dt.strftime('%Y-%m-%d')
        layers['hour'] = layers['timestamp'].dt.hour
        layers = layers.rename(columns={
            'cloud_cover_low_percent': 'cloud_cover_low_pct',
            'cloud_cover_mid_percent': 'cloud_cover_mid_pct',
        })
        keep = [c for c in ('day', 'hour', 'cloud_cover_low_pct', 'cloud_cover_mid_pct') if c in layers.columns]
        feats = feats.merge(layers[keep].drop_duplicates(['day', 'hour'], keep='last'),
                            on=['day', 'hour'], how='left')
        for c in ('cloud_cover_low_pct', 'cloud_cover_mid_pct'):
            if c not in feats.columns:
                feats[c] = feats['cloud_cover_pct']
            feats[c] = feats[c].fillna(feats['cloud_cover_pct'])
        feats = add_clearness_features(feats, latitude=lat, longitude=lon)
        for mname, pr in predictors.items():
            daily = predict_daily(pr, feats).set_index('day')['predicted_kwh']
            for d in days:
                rows[d][f'{mname}_{wk}'] = float(daily.get(d, np.nan))

    out = pd.DataFrame(rows.values())
    out['RF_half'] = (out['RF_I'] + out['RF_U']) / 2
    out['CS4_half'] = (out['CS4_I'] + out['CS4_U']) / 2
    apps = [resolve_actual_pv_total(d, db) for d in days]
    out['app_kwh'] = [a[0] for a in apps]
    out['app_src'] = [a[1] for a in apps]

    stamp = datetime.now().strftime('%Y%m%d_%H%M')
    path = ROOT / f'data/processed/oneshot_shadow_icon_ukmo_{stamp}.csv'
    out.to_csv(path, index=False)
    sky = pd.DataFrame(sky_rows)
    sky.to_csv(ROOT / f'data/processed/oneshot_shadow_icon_ukmo_{stamp}_sky.csv', index=False)

    pd.set_option('display.width', 200)
    print(out.round(2).to_string(index=False))
    print()
    print(sky.round(1).to_string(index=False))
    print(f'\n✓ {path.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
