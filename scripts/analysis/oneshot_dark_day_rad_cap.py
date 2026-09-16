#!/usr/bin/env python3
"""Gate: cap fizyczny na ciemnych dniach (archiwum Open-Meteo + FoxESS).

PR=0,85 stałe (nie fitowane). Trigger: cloud 6–20 ≥95% AND GHI <1500 AND opad ≥3 mm.

    PYTHONPATH=$PWD ./venv/bin/python scripts/analysis/oneshot_dark_day_rad_cap.py
    PYTHONPATH=$PWD ./venv/bin/python scripts/analysis/oneshot_dark_day_rad_cap.py --snapshots
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')

KWP = float(os.getenv('PV_SYSTEM_KWP', '5.39'))
PR = float(os.getenv('DARK_DAY_PR', '0.85'))
CLOUD_MIN = 95.0
RAD_MAX = 1500.0
PRECIP_MIN = 3.0
DB = os.getenv('DATABASE_PATH', str(ROOT / 'data/energy_model.db'))
FORECASTS = ROOT / 'data/processed/forecasts'
OUT_CSV = ROOT / 'data/processed/oneshot_dark_day_rad_cap_gate.csv'


def ape_pct(pred: float, actual: float) -> float:
    if actual <= 0:
        return float('nan')
    return 100.0 * (pred - actual) / actual


def mape(series: pd.Series) -> float:
    s = series.abs().dropna()
    return float(s.mean()) if len(s) else float('nan')


def archive_daily(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        '''
        SELECT date(timestamp) AS day,
               AVG(cloud_cover_percent) AS cloud,
               SUM(precipitation_mm) AS precip,
               SUM(solar_radiation_wm2) AS rad
        FROM weather_data
        WHERE data_source = 'OpenMeteo-archive'
          AND CAST(strftime('%H', timestamp) AS INT) BETWEEN 6 AND 20
        GROUP BY 1
        ''',
        conn,
    )


def trigger_row(cloud: float, rad: float, precip: float) -> bool:
    return cloud >= CLOUD_MIN and rad < RAD_MAX and precip >= PRECIP_MIN


def cap_hourly(raw: pd.Series, rad: pd.Series) -> pd.Series:
    phys = KWP * (pd.to_numeric(rad, errors='coerce') / 1000.0) * PR
    return pd.concat([pd.to_numeric(raw, errors='coerce'), phys], axis=1).min(axis=1)


def predict_day(predictor, day: str, db_path: str) -> pd.DataFrame:
    as_of = datetime.fromisoformat(f'{day}T05:00:00')
    return predictor.predict_days(
        days_ahead=1,
        db_path=db_path,
        from_date=date.fromisoformat(day),
        hybrid_today=False,
        use_actual_pv=False,
        as_of=as_of,
    )


def summarize(tag: str, df: pd.DataFrame) -> str:
    if df.empty:
        return f'{tag}: n=0'
    return (
        f'{tag}: n={len(df)}  MAPE RF {mape(df["APE_RF"]):.1f}%  '
        f'CS4 {mape(df["APE_CS4"]):.1f}%  cap {mape(df["APE_cap"]):.1f}%  '
        f'|APE|>100% RF {int((df["APE_RF"].abs()>=100).sum())} → cap {int((df["APE_cap"].abs()>=100).sum())}'
    )


def run_gate() -> pd.DataFrame:
    from src.data.foxess_pv_total import resolve_actual_pv_total
    from src.models import pv_hourly_predictor as php
    from src.models.pv_hourly_predictor import PVHourlyPredictor

    def archive_only(db_path, start, end, location=None):
        return php.load_weather_hourly(
            db_path, start, end, location, data_source_like='OpenMeteo-archive',
        )

    php.load_forecast_weather_hourly = archive_only

    conn = sqlite3.connect(DB)
    daily = archive_daily(conn)
    conn.close()
    daily['day'] = daily['day'].astype(str)
    daily = daily[daily['day'] >= '2025-09-01'].copy()
    daily['dark'] = (daily['cloud'] >= CLOUD_MIN) & (daily['rad'] < RAD_MAX)
    daily['wet'] = daily['precip'] >= PRECIP_MIN
    daily['bucket'] = np.where(
        daily['dark'] & daily['wet'],
        'dark_wet',
        np.where(daily['dark'], 'dark_dry', np.where(daily['cloud'] >= 80, 'mix80', 'other')),
    )
    candidates = sorted(
        set(daily.loc[daily.bucket == 'dark_wet', 'day'])
        | set(daily.loc[daily.bucket == 'dark_dry', 'day'])
        | set(daily.loc[daily.bucket == 'mix80'].nlargest(15, 'rad')['day'])
        | set(daily.loc[daily.bucket == 'other'].nsmallest(8, 'cloud')['day'])
    )

    actuals = []
    for day in candidates:
        kwh, src = resolve_actual_pv_total(day, DB)
        if kwh is None or kwh <= 0:
            continue
        actuals.append({'day': day, 'Fox': float(kwh), 'fox_src': src})
    act = pd.DataFrame(actuals)
    daily = daily.merge(act, on='day', how='inner')
    target_days = sorted(daily['day'].tolist())

    rf = PVHourlyPredictor()
    rf.load()
    cs4 = PVHourlyPredictor('models/pv_hourly_model_cs4.joblib')
    cs4.load()

    rows = []
    for i, day in enumerate(target_days, 1):
        meta = daily[daily.day == day].iloc[0]
        print(f'  [{i}/{len(target_days)}] {day} {meta.bucket} Fox={meta.Fox:.1f}', flush=True)
        try:
            pred_rf = predict_day(rf, day, DB)
            pred_cs4 = predict_day(cs4, day, DB)
        except Exception as exc:
            print(f'    skip: {exc}')
            continue
        if pred_rf.empty:
            print('    skip: pusta prognoza RF')
            continue
        rf_sum = float(pred_rf['predicted_kwh_raw'].sum())
        cap_sum = float(cap_hourly(pred_rf['predicted_kwh_raw'], pred_rf['radiation_wm2']).sum())
        cs4_sum = float(pred_cs4['predicted_kwh_raw'].sum()) if not pred_cs4.empty else float('nan')
        fire = trigger_row(float(meta.cloud), float(meta.rad), float(meta.precip))
        cap_applied = cap_sum if fire else rf_sum
        fox = float(meta.Fox)
        rows.append(
            {
                'day': day,
                'bucket': meta.bucket,
                'trigger': 'TAK' if fire else 'nie',
                'cloud': round(float(meta.cloud), 1),
                'precip': round(float(meta.precip), 1),
                'rad': round(float(meta.rad), 0),
                'Fox': round(fox, 2),
                'RF': round(rf_sum, 2),
                'CS4': round(cs4_sum, 2) if pd.notna(cs4_sum) else None,
                'cap': round(float(cap_applied), 2),
                'APE_RF': round(ape_pct(rf_sum, fox), 1),
                'APE_CS4': round(ape_pct(cs4_sum, fox), 1) if pd.notna(cs4_sum) else None,
                'APE_cap': round(ape_pct(float(cap_applied), fox), 1),
            }
        )

    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)
    return out


def verdict(out: pd.DataFrame) -> str:
    wet = out[out.bucket == 'dark_wet']
    dry = out[out.bucket == 'dark_dry']
    ctrl = out[out.bucket.isin(['mix80', 'other'])]
    mape_rf = mape(wet['APE_RF'])
    mape_cap = mape(wet['APE_cap'])
    mape_cs4 = mape(wet['APE_CS4'])
    ctrl_delta = mape(ctrl['APE_cap']) - mape(ctrl['APE_RF']) if len(ctrl) else 0.0
    # ACCEPT: dark_wet MAPE cap wyraźnie niższe, kontrola bez regresji (trigger off → delta 0)
    if len(wet) < 5:
        return 'REVIEW (za mało dark_wet po udanym predict)'
    if mape_cap <= mape_rf - 15 and abs(ctrl_delta) < 1:
        return 'ACCEPT overlay (cap tylko na trigger; nie primary RF)'
    if mape_cap < mape_rf and abs(ctrl_delta) < 1:
        return 'REVIEW (cap pomaga, ale zysk <15 pp MAPE)'
    return 'REJECT'


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshots', action='store_true', help='tylko replay 25.08/11.09 z CSV launchd')
    args = parser.parse_args()
    if args.snapshots:
        from scripts.analysis import oneshot_dark_day_rad_cap as selfmod  # noqa: F401
        print('Użyj poprzedniego runu snapshotów albo usuń --snapshots i puść gate.')
        return

    print(f'GATE cap  kWp={KWP} PR={PR}')
    print(f'trigger: cloud≥{CLOUD_MIN:.0f}%  rad<{RAD_MAX:.0f}  precip≥{PRECIP_MIN} mm')
    print('pogoda: OpenMeteo-archive (oracle GHI, nie NWP z 05:00)')
    print()
    out = run_gate()
    if out.empty:
        print('Brak wierszy.')
        return
    print()
    print(out.to_string(index=False))
    print()
    wet = out[out.bucket == 'dark_wet']
    dry = out[out.bucket == 'dark_dry']
    ctrl = out[out.bucket.isin(['mix80', 'other'])]
    print(summarize('dark_wet', wet))
    print(summarize('dark_dry (trigger OFF, precip<3)', dry))
    print(summarize('kontrola mix/jasne (trigger OFF)', ctrl))
    print()
    v = verdict(out)
    print(f'Werdykt: {v}')
    print(f'CSV: {OUT_CSV}')


if __name__ == '__main__':
    main()
