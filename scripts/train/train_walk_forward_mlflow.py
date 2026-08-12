#!/usr/bin/env python
"""
Walk-forward miesięczny → MLflow (Lekcja 38).

Dla każdego miesiąca testowego M:
  train = wszystkie dni < pierwszy dzień M
  test  = dni w miesiącu M
  (expanding window; min. 90 dni treningu)

Modele:
  - RF production (ICON, 16 cech) — baseline produkcyjny
  - XGB + TS (ICON, 16+8 cech szeregów)
  - UKMO XGB CS4 (19 cech) — faworyt z MLflow

Uruchomienie:
    python scripts/train/train_walk_forward_mlflow.py --mlflow
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')
os.environ.setdefault('MPLCONFIGDIR', '/tmp/mpl')
os.environ.setdefault('MPLBACKEND', 'Agg')
os.environ.setdefault('PANEL_GEOMETRY_FEATURES', '1')

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

from scripts.train.train_holdout_and_ts_mlflow import (
    TS_FEATURE_COLUMNS,
    PEAK_HOURS,
    _rf_pipe,
    _xgb_pipe,
    add_nwp_time_series_features,
)
from scripts.train.train_hourly_model_tuning import MLFLOW_EXPERIMENT
from scripts.train.train_ukmo_mlflow_compare import build_ukmo_training_frame
from src.features.pv_features_hourly_extended import (
    HOURLY_FEATURE_COLUMNS_CS4,
    HOURLY_FEATURE_COLUMNS_PRODUCTION,
    TARGET_COLUMN,
    load_hourly_training_frame_extended,
)
from src.models.pv_hourly_predictor import _metrics

MIN_TRAIN_DAYS = 90


def _month_starts(days: pd.Series) -> list[str]:
    dts = pd.to_datetime(sorted(days.astype(str).unique()))
    months = sorted({d.to_period('M') for d in dts})
    # pomijamy pierwszy miesiąc — za mało historii przed nim
    return [str(m) for m in months[1:]]


def _eval_fold(pipe, frame, cols, train_mask, test_mask) -> dict:
    X_tr = frame.loc[train_mask, cols]
    y_tr = frame.loc[train_mask, TARGET_COLUMN]
    X_te = frame.loc[test_mask, cols]
    y_te = frame.loc[test_mask, TARGET_COLUMN]
    meta = frame.loc[test_mask, ['day', 'hour']].copy()

    pipe.fit(X_tr, y_tr)
    pred_tr = pipe.predict(X_tr)
    pred_te = pipe.predict(X_te)
    tr = _metrics(y_tr, pred_tr)
    te = _metrics(y_te, pred_te)
    gap = te['mae'] - tr['mae']

    meta['y_true'] = y_te.values
    meta['y_pred'] = pred_te
    meta['abs_err'] = (meta['y_true'] - meta['y_pred']).abs()
    daily_true = meta.groupby('day')['y_true'].sum()
    daily_pred = meta.groupby('day')['y_pred'].sum()
    peak = meta[meta['hour'].isin(PEAK_HOURS)]
    high_days = daily_true[daily_true >= 30].index
    high = meta[meta['day'].isin(high_days)]

    return {
        'train_mae': tr['mae'],
        'test_mae': te['mae'],
        'gap': gap,
        'daily_mae': mean_absolute_error(daily_true, daily_pred),
        'daily_r2': r2_score(daily_true, daily_pred) if len(daily_true) > 1 else float('nan'),
        'peak_mae': float(peak['abs_err'].mean()) if len(peak) else float('nan'),
        'high_day_mae': float(high['abs_err'].mean()) if len(high) else float('nan'),
        'n_train_days': int(frame.loc[train_mask, 'day'].nunique()),
        'n_test_days': int(frame.loc[test_mask, 'day'].nunique()),
        'n_high_days': int(len(high_days)),
    }


def run_walk_forward(name: str, frame: pd.DataFrame, cols: list[str], make_pipe, weather: str, log_mlflow: bool) -> pd.DataFrame:
    frame = frame.copy()
    frame['day'] = frame['day'].astype(str)
    months = _month_starts(frame['day'])
    rows = []
    print(f'\n{"=" * 72}\nWALK-FORWARD: {name} | {weather} | {len(cols)} cech | miesiące={months}\n{"=" * 72}')

    for month in months:
        period = pd.Period(month, freq='M')
        start = period.start_time.date().isoformat()
        end = period.end_time.date().isoformat()
        train_mask = frame['day'] < start
        test_mask = (frame['day'] >= start) & (frame['day'] <= end)
        n_train_days = frame.loc[train_mask, 'day'].nunique()
        n_test = test_mask.sum()
        if n_train_days < MIN_TRAIN_DAYS or n_test < 20:
            print(f'  skip {month}: train_days={n_train_days}, test_h={n_test}')
            continue

        ev = _eval_fold(make_pipe(), frame, cols, train_mask, test_mask)
        print(
            f'  {month}: train_d={ev["n_train_days"]:3d} test_d={ev["n_test_days"]:2d} '
            f'train={ev["train_mae"]:.3f} test={ev["test_mae"]:.3f} gap={ev["gap"]:.3f} '
            f'daily={ev["daily_mae"]:.2f} peak={ev["peak_mae"]:.3f} '
            f'high(≥30kWh)={ev["high_day_mae"]:.3f} n_high={ev["n_high_days"]}'
        )
        row = {'model': name, 'weather': weather, 'month': month, **ev}
        rows.append(row)

        if log_mlflow:
            import mlflow
            mlflow.set_experiment(MLFLOW_EXPERIMENT)
            with mlflow.start_run(run_name=f'wf_{name}_{month}'):
                mlflow.log_params({
                    'split': 'walk_forward_monthly',
                    'test_month': month,
                    'model_name': name,
                    'weather_model': weather,
                    'n_features': len(cols),
                    'min_train_days': MIN_TRAIN_DAYS,
                    'n_train_days': ev['n_train_days'],
                    'n_test_days': ev['n_test_days'],
                })
                mlflow.log_metrics({
                    'train_mae': ev['train_mae'],
                    'test_mae': ev['test_mae'],
                    'gap': ev['gap'],
                    'daily_mae': ev['daily_mae'],
                    'peak_mae': ev['peak_mae'],
                    'high_day_mae': ev['high_day_mae'],
                })
                mlflow.set_tag('split', 'walk_forward_monthly')
                mlflow.set_tag('model_name', name)
                mlflow.set_tag('weather_model', weather)

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--mlflow', action='store_true')
    args = parser.parse_args()

    lat = float(os.getenv('WEATHER_LAT', '50.06'))
    lon = float(os.getenv('WEATHER_LON', '19.94'))

    print('[1] ICON frame + TS...')
    icon = load_hourly_training_frame_extended(
        start_date='2025-06-01', end_date='2026-07-28', latitude=lat, longitude=lon,
    )
    icon = add_nwp_time_series_features(icon)

    print('[2] UKMO frame...')
    ukmo = build_ukmo_training_frame('2025-06-01', '2026-07-28', lat, lon)

    parts = [
        run_walk_forward(
            'rf_production', icon, HOURLY_FEATURE_COLUMNS_PRODUCTION, _rf_pipe, 'icon_seamless', args.mlflow,
        ),
        run_walk_forward(
            'xgb_production_ts',
            icon,
            HOURLY_FEATURE_COLUMNS_PRODUCTION + TS_FEATURE_COLUMNS,
            _xgb_pipe,
            'icon_seamless',
            args.mlflow,
        ),
        run_walk_forward(
            'ukmo_xgb_cs4', ukmo, HOURLY_FEATURE_COLUMNS_CS4, _xgb_pipe, 'ukmo_seamless', args.mlflow,
        ),
    ]
    summary = pd.concat(parts, ignore_index=True)
    out = ROOT / 'data/processed/walk_forward_monthly.csv'
    summary.to_csv(out, index=False)

    print('\n' + '=' * 72)
    print('ŚREDNIE PO FOLDACH (walk-forward)')
    print('=' * 72)
    agg = (
        summary.groupby(['model', 'weather'], as_index=False)
        .agg(
            folds=('month', 'count'),
            test_mae=('test_mae', 'mean'),
            gap=('gap', 'mean'),
            daily_mae=('daily_mae', 'mean'),
            peak_mae=('peak_mae', 'mean'),
            high_day_mae=('high_day_mae', 'mean'),
        )
        .sort_values('test_mae')
    )
    print(agg.to_string(index=False))
    print(f'\n✓ {out}')

    if args.mlflow:
        import mlflow
        mlflow.set_experiment(MLFLOW_EXPERIMENT)
        for _, r in agg.iterrows():
            with mlflow.start_run(run_name=f'wf_summary_{r["model"]}'):
                mlflow.log_params({
                    'split': 'walk_forward_monthly_summary',
                    'model_name': r['model'],
                    'weather_model': r['weather'],
                    'n_folds': int(r['folds']),
                })
                mlflow.log_metrics({
                    'test_mae': float(r['test_mae']),
                    'gap': float(r['gap']),
                    'daily_mae': float(r['daily_mae']),
                    'peak_mae': float(r['peak_mae']),
                    'high_day_mae': float(r['high_day_mae']),
                })
                mlflow.log_artifact(str(out))
                mlflow.set_tag('split', 'walk_forward_monthly_summary')
        print(f'✓ MLflow summaries → {MLFLOW_EXPERIMENT}')


if __name__ == '__main__':
    main()
