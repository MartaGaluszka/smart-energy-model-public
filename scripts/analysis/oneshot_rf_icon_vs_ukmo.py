#!/usr/bin/env python
"""
Oneshot RF: produkcja dzienna przy pogodzie ICON vs UKMO (ten sam .joblib).

Bez zapisu do DB / bez zmiany OPENMETEO_MODEL / launchd.

Uruchomienie:
    PYTHONPATH=$PWD python scripts/analysis/oneshot_rf_icon_vs_ukmo.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')

from src.data.foxess_pv_total import resolve_actual_pv_total
from src.data.weather_api import OpenMeteoClient
from src.features.pv_features_hourly_extended import calculate_sun_features
from src.models.pv_hourly_predictor import (
    PVHourlyPredictor,
    _daily_weather_from_hourly,
    _forecast_fog_flags,
    _forecast_snow_flags,
)

OUT = ROOT / 'data/processed/oneshot_rf_icon_vs_ukmo_daily.csv'
DEFAULT_DAYS = ['2026-07-21', '2026-07-22', '2026-07-23', '2026-07-24']


def _api_to_hourly(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out['timestamp'] = pd.to_datetime(out['timestamp'])
    out['day'] = out['timestamp'].dt.strftime('%Y-%m-%d')
    out['hour'] = out['timestamp'].dt.hour
    out = out.rename(columns={
        'temperature_celsius': 'temp_c',
        'humidity_percent': 'humidity_pct',
        'cloud_cover_percent': 'cloud_cover_pct',
        'solar_radiation_wm2': 'radiation_wm2',
        'precipitation_mm': 'precip_mm',
    })
    cols = [
        'day', 'hour', 'temp_c', 'humidity_pct', 'cloud_cover_pct',
        'radiation_wm2', 'wind_speed_ms', 'visibility_m', 'snow_depth_m', 'precip_mm',
    ]
    for c in cols:
        if c not in out.columns:
            out[c] = np.nan
    return out[cols].drop_duplicates(['day', 'hour'], keep='last')


def features_from_weather(
    weather: pd.DataFrame,
    days: list[str],
    lat: float,
    lon: float,
) -> pd.DataFrame:
    records = [{'day': d, 'hour': h} for d in days for h in range(5, 22)]
    grid = pd.DataFrame(records)
    w = weather[weather['day'].isin(days)].copy()
    df = grid.merge(w, on=['day', 'hour'], how='left')
    df = calculate_sun_features(df, latitude=lat, longitude=lon)

    daily = _daily_weather_from_hourly(w)
    if not daily.empty:
        df = df.merge(_forecast_snow_flags(daily), on='day', how='left')
        df = df.merge(_forecast_fog_flags(daily), on='day', how='left')
    for c in ('snow_on_panels', 'snow_on_panels_prev', 'likely_fog_day'):
        if c not in df.columns:
            df[c] = 0
        df[c] = df[c].fillna(0).astype(int)

    df = df.loc[df['is_daylight'] == 1].copy()
    df = df.loc[df['radiation_wm2'].notna()].reset_index(drop=True)
    return df


def predict_daily(predictor: PVHourlyPredictor, features: pd.DataFrame) -> pd.DataFrame:
    X = features[predictor.feature_columns]
    pred = np.clip(predictor.pipeline.predict(X), 0, None)
    out = features[['day', 'hour']].copy()
    out['predicted_kwh'] = pred
    return out.groupby('day', as_index=False)['predicted_kwh'].sum()


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description='Oneshot RF: ICON vs UKMO')
    p.add_argument('--start', default=DEFAULT_DAYS[0])
    p.add_argument('--end', default=DEFAULT_DAYS[-1])
    args = p.parse_args()
    days = pd.date_range(args.start, args.end, freq='D').strftime('%Y-%m-%d').tolist()

    lat = float(os.getenv('WEATHER_LAT', '50.06'))
    lon = float(os.getenv('WEATHER_LON', '19.94'))
    db = os.getenv('DATABASE_PATH', str(ROOT / 'data/energy_model.db'))
    if not Path(db).is_absolute():
        db = str(ROOT / db)

    print('=' * 72)
    print('ONESHOT RF: ICON vs UKMO (ten sam joblib) — bez produkcji')
    print(f'GPS {lat}, {lon}  |  dni {days[0]} → {days[-1]}')
    print('=' * 72)

    predictor = PVHourlyPredictor()
    predictor.load()
    print(f'Model: {predictor.feature_columns and len(predictor.feature_columns)} cech')

    daily_rows = []
    hourly_rows = []

    for model in ('icon_seamless', 'ukmo_seamless'):
        print(f'\n[fetch archive] {model}...')
        client = OpenMeteoClient(lat, lon, model=model)
        raw = client.fetch_archive(days[0], days[-1])
        weather = _api_to_hourly(raw)
        print(f'  godzin API: {len(weather)}')
        feats = features_from_weather(weather, days, lat, lon)
        print(f'  wierszy cech (daylight): {len(feats)}')
        daily = predict_daily(predictor, feats)
        daily['weather_model'] = model
        daily_rows.append(daily)

        h = feats[['day', 'hour']].copy()
        h['predicted_kwh'] = np.clip(
            predictor.pipeline.predict(feats[predictor.feature_columns]), 0, None
        )
        h['weather_model'] = model
        hourly_rows.append(h)

    daily = pd.concat(daily_rows, ignore_index=True)
    wide = daily.pivot(index='day', columns='weather_model', values='predicted_kwh').reset_index()
    wide['delta_ukmo_minus_icon'] = wide['ukmo_seamless'] - wide['icon_seamless']

    apps = []
    for day in days:
        app, src = resolve_actual_pv_total(day, db)
        apps.append({'day': day, 'app_kwh': app, 'app_src': src})
    apps_df = pd.DataFrame(apps)
    wide = wide.merge(apps_df, on='day', how='left')

    def _acc(pred, act):
        if act is None or (isinstance(act, float) and np.isnan(act)) or act == 0:
            return np.nan
        return 100.0 * (1.0 - abs(pred - act) / act)

    wide['dokl_icon'] = [
        _acc(i, a) for i, a in zip(wide['icon_seamless'], wide['app_kwh'])
    ]
    wide['dokl_ukmo'] = [
        _acc(u, a) for u, a in zip(wide['ukmo_seamless'], wide['app_kwh'])
    ]

    print('\n' + '=' * 72)
    print('PROGNOZA DZIENNA (raw RF, daylight)')
    print('=' * 72)
    print(
        f'{"dzień":12s} {"ICON":>8s} {"UKMO":>8s} {"Δ":>7s} '
        f'{"app":>8s} {"dokł.I":>8s} {"dokł.U":>8s}'
    )
    for _, r in wide.iterrows():
        app = r['app_kwh']
        app_s = f'{app:8.1f}' if pd.notna(app) else f'{"—":>8s}'
        di = f'{r["dokl_icon"]:7.0f}%' if pd.notna(r['dokl_icon']) else f'{"—":>8s}'
        du = f'{r["dokl_ukmo"]:7.0f}%' if pd.notna(r['dokl_ukmo']) else f'{"—":>8s}'
        print(
            f'{r["day"]:12s} {r["icon_seamless"]:8.1f} {r["ukmo_seamless"]:8.1f} '
            f'{r["delta_ukmo_minus_icon"]:+7.1f} {app_s} {di} {du}'
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wide.to_csv(OUT, index=False)
    hourly = pd.concat(hourly_rows, ignore_index=True)
    hourly_out = ROOT / 'data/processed/oneshot_rf_icon_vs_ukmo_hourly.csv'
    hourly.to_csv(hourly_out, index=False)
    print(f'\n✓ {OUT.relative_to(ROOT)}')
    print(f'✓ {hourly_out.relative_to(ROOT)}')
    print('\nUwaga: model uczony na ICON — UKMO = transfer na inną pogodę (oneshot).')
    print('Dziś (24.07) app może być niepełne przed closeoutem.')


if __name__ == '__main__':
    main()
