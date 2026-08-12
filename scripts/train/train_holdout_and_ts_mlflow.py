#!/usr/bin/env python
"""
Holdout czasowy + cechy szeregów czasowych (Lekcja 38) → MLflow.

1) HOLDOUT (jak historyczne odrzucenie XGB):
   train: day < 2026-06-01
   test:  day >= 2026-06-01
   Modele: RF production, XGB production, XGB+TS, (opcjonalnie UKMO XGB CS4)

2) CECHY TS (tylko z prognozy NWP — bez lag targetu PV = bez leakage):
   - lag_1 radiation / cloud
   - rolling mean/std 3h radiation / cloud (z shift(1) w obrębie dnia)
   - diff_1 radiation / cloud

3) Metryki dodatkowe pod błędy szczytu (jak 28.07 12–16):
   - peak_mae (godziny 10–16)
   - case_2026-07-28 peak hours MAE

Uruchomienie:
    python scripts/train/train_holdout_and_ts_mlflow.py --mlflow
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
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor

from scripts.train.train_hourly_model_tuning import MLFLOW_EXPERIMENT
from src.features.nwp_time_series import TS_FEATURE_COLUMNS, add_nwp_time_series_features
from src.features.pv_features_hourly_extended import (
    HOURLY_FEATURE_COLUMNS_CS4,
    HOURLY_FEATURE_COLUMNS_PRODUCTION,
    TARGET_COLUMN,
    load_hourly_training_frame_extended,
)
from src.models.pv_hourly_predictor import (
    RF_MAX_DEPTH,
    RF_MAX_FEATURES,
    RF_MIN_SAMPLES_LEAF,
    RF_MIN_SAMPLES_SPLIT,
    RF_N_ESTIMATORS,
    _metrics,
)

HOLDOUT_CUT = '2026-06-01'
PEAK_HOURS = list(range(10, 17))  # 10:00–16:00 — godziny największej produkcji
CASE_DAY = '2026-07-28'


def _rf_pipe() -> Pipeline:
    return Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('model', RandomForestRegressor(
            n_estimators=RF_N_ESTIMATORS,
            max_depth=RF_MAX_DEPTH,
            min_samples_leaf=RF_MIN_SAMPLES_LEAF,
            min_samples_split=RF_MIN_SAMPLES_SPLIT,
            max_features=RF_MAX_FEATURES,
            random_state=42,
            n_jobs=-1,
        )),
    ])


def _xgb_pipe() -> Pipeline:
    # Parametry zwycięskiego uregularyzowanego XGB z MLflow (min-gap)
    return Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('model', XGBRegressor(
            n_estimators=200,
            max_depth=3,
            learning_rate=0.05,
            subsample=1.0,
            colsample_bytree=1.0,
            min_child_weight=10,
            objective='reg:absoluteerror',
            random_state=42,
            n_jobs=-1,
        )),
    ])


def _eval_split(pipe, X_tr, y_tr, X_te, y_te, meta_te: pd.DataFrame) -> dict:
    pipe.fit(X_tr, y_tr)
    pred_tr = pipe.predict(X_tr)
    pred_te = pipe.predict(X_te)
    tr = _metrics(y_tr, pred_tr)
    te = _metrics(y_te, pred_te)
    gap = te['mae'] - tr['mae']

    m = meta_te.copy()
    m['y_true'] = y_te.values
    m['y_pred'] = pred_te
    m['abs_err'] = (m['y_true'] - m['y_pred']).abs()

    daily_true = m.groupby('day')['y_true'].sum()
    daily_pred = m.groupby('day')['y_pred'].sum()
    daily_mae = mean_absolute_error(daily_true, daily_pred)
    daily_r2 = r2_score(daily_true, daily_pred)

    peak = m[m['hour'].isin(PEAK_HOURS)]
    peak_mae = float(peak['abs_err'].mean()) if len(peak) else float('nan')

    case = m[m['day'] == CASE_DAY]
    case_peak = case[case['hour'].isin(PEAK_HOURS)]
    case_peak_mae = float(case_peak['abs_err'].mean()) if len(case_peak) else float('nan')
    case_hours = []
    if not case_peak.empty:
        for r in case_peak.sort_values('hour').itertuples(index=False):
            case_hours.append({
                'hour': int(r.hour),
                'y_true': round(float(r.y_true), 2),
                'y_pred': round(float(r.y_pred), 2),
                'err': round(float(r.y_true - r.y_pred), 2),
            })

    # Werdykt jak przy historycznym odrzuceniu XGB (gap na holdoucie)
    if gap < 0.15:
        verdict = 'nie_przeuczony'
    elif gap < 0.35:
        verdict = 'lekkie_przeuczenie'
    else:
        verdict = 'przeuczony'

    return {
        'pipeline': pipe,
        'train_mae': tr['mae'],
        'test_mae': te['mae'],
        'gap': gap,
        'daily_mae': daily_mae,
        'daily_r2': daily_r2,
        'peak_mae': peak_mae,
        'case_peak_mae': case_peak_mae,
        'case_hours': case_hours,
        'verdict': verdict,
        'n_train': len(y_tr),
        'n_test': len(y_te),
        'n_test_days': int(m['day'].nunique()),
    }


def _log_mlflow(run_name: str, params: dict, metrics: dict, tags: dict, pipe) -> None:
    import mlflow
    import mlflow.sklearn

    mlflow.set_experiment(MLFLOW_EXPERIMENT)
    with mlflow.start_run(run_name=run_name):
        mlflow.log_params(params)
        mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, (int, float)) and np.isfinite(v)})
        for k, v in tags.items():
            mlflow.set_tag(k, v)
        mlflow.sklearn.log_model(pipe, name='model')


def run_holdout_icon(frame: pd.DataFrame, log_mlflow: bool) -> list[dict]:
    frame = frame.copy()
    frame['day'] = frame['day'].astype(str)
    train_mask = frame['day'] < HOLDOUT_CUT
    test_mask = frame['day'] >= HOLDOUT_CUT
    meta_te = frame.loc[test_mask, ['day', 'hour']]

    configs = [
        ('holdout_rf_production', 'rf', HOURLY_FEATURE_COLUMNS_PRODUCTION, False),
        ('holdout_xgb_production', 'xgb', HOURLY_FEATURE_COLUMNS_PRODUCTION, False),
        ('holdout_xgb_production_ts', 'xgb', HOURLY_FEATURE_COLUMNS_PRODUCTION + TS_FEATURE_COLUMNS, True),
        ('holdout_rf_production_ts', 'rf', HOURLY_FEATURE_COLUMNS_PRODUCTION + TS_FEATURE_COLUMNS, True),
        ('holdout_xgb_cs4_ts', 'xgb', HOURLY_FEATURE_COLUMNS_CS4 + TS_FEATURE_COLUMNS, True),
    ]

    results = []
    for run_name, model_type, cols, use_ts in configs:
        missing = [c for c in cols if c not in frame.columns]
        if missing:
            raise KeyError(missing)
        X_tr = frame.loc[train_mask, cols]
        y_tr = frame.loc[train_mask, TARGET_COLUMN]
        X_te = frame.loc[test_mask, cols]
        y_te = frame.loc[test_mask, TARGET_COLUMN]
        pipe = _rf_pipe() if model_type == 'rf' else _xgb_pipe()

        print(f'\n=== {run_name} | cech={len(cols)} | train<{HOLDOUT_CUT} ===')
        ev = _eval_split(pipe, X_tr, y_tr, X_te, y_te, meta_te)
        print(
            f'  train MAE={ev["train_mae"]:.3f}  holdout MAE={ev["test_mae"]:.3f}  '
            f'gap={ev["gap"]:.3f}  daily={ev["daily_mae"]:.3f}  peak10-16={ev["peak_mae"]:.3f}  '
            f'{CASE_DAY} peak={ev["case_peak_mae"]:.3f}  → {ev["verdict"]}'
        )
        if ev['case_hours']:
            print(f'  {CASE_DAY} (10–16):')
            for h in ev['case_hours']:
                print(f'    {h["hour"]:02d}:00  pred={h["y_pred"]:.2f}  true={h["y_true"]:.2f}  err={h["err"]:+.2f}')

        if log_mlflow:
            _log_mlflow(
                run_name,
                {
                    'split': 'chronological_holdout',
                    'holdout_cut': HOLDOUT_CUT,
                    'feature_set': 'production_ts' if use_ts else ('cs4_ts' if 'cs4' in run_name else 'production'),
                    'n_features': len(cols),
                    'model_type': 'random_forest' if model_type == 'rf' else 'xgboost',
                    'weather_model': 'icon_seamless',
                    'ts_features': str(use_ts),
                },
                {
                    'train_mae': ev['train_mae'],
                    'test_mae': ev['test_mae'],
                    'gap': ev['gap'],
                    'daily_mae': ev['daily_mae'],
                    'daily_r2': ev['daily_r2'],
                    'peak_mae': ev['peak_mae'],
                    'case_20260728_peak_mae': ev['case_peak_mae'],
                },
                {
                    'split': 'chronological_holdout',
                    'verdict': ev['verdict'],
                    'model_type': 'random_forest' if model_type == 'rf' else 'xgboost',
                },
                ev['pipeline'],
            )
            print(f'  ✓ MLflow: {run_name}')

        results.append({'run_name': run_name, **{k: v for k, v in ev.items() if k not in ('pipeline', 'case_hours')}})
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--mlflow', action='store_true')
    args = parser.parse_args()

    lat = float(os.getenv('WEATHER_LAT', '50.06'))
    lon = float(os.getenv('WEATHER_LON', '19.94'))

    print('[1] Ładowanie ramki ICON + cechy TS (Lekcja 38)...')
    frame = load_hourly_training_frame_extended(
        start_date='2025-06-01',
        end_date='2026-07-28',
        latitude=lat,
        longitude=lon,
    )
    frame = add_nwp_time_series_features(frame)
    print(f'✓ {len(frame)} h, {frame["day"].nunique()} dni (+ {len(TS_FEATURE_COLUMNS)} cech TS)')

    n_holdout = (frame['day'].astype(str) >= HOLDOUT_CUT).sum()
    print(f'  Holdout {HOLDOUT_CUT}+: {n_holdout} h')

    results = run_holdout_icon(frame, args.mlflow)
    summary = pd.DataFrame(results).sort_values(['gap', 'peak_mae'])
    out = ROOT / 'data/processed/holdout_ts_comparison.csv'
    summary.to_csv(out, index=False)
    print('\n' + '=' * 72)
    print('HOLDDOUT + TS — podsumowanie (sort: gap, peak_mae)')
    print('=' * 72)
    cols = ['run_name', 'train_mae', 'test_mae', 'gap', 'daily_mae', 'peak_mae', 'case_peak_mae', 'verdict']
    print(summary[cols].to_string(index=False))
    print(f'\n✓ {out}')


if __name__ == '__main__':
    main()
