#!/usr/bin/env python
"""
Eksperyment: przedziały czasowe pod błędy godzin szczytu (Lekcja 38).

Hipoteza prowadzącego / projektu: nie brakuje „jeszcze jednej cechy pogody”,
tylko model uczy się za słabo na przedziale, który boli operacyjnie
(10:00–16:00, szczególnie dni ≥30 kWh).

Warianty (ten sam split chronologiczny holdout ≥2026-06-01, ICON):
  1) baseline_xgb          — XGB uregularyzowany, bez wag
  2) xgb_peak_weight       — waga ×3 dla godzin 10–16
  3) xgb_peak_and_highday  — ×3 peak + dodatkowe ×2 gdy dzień ≥30 kWh (w train)
  4) xgb_peak_only_model   — trenuj TYLKO na godzinach 10–16 (osobny model szczytu)
  5) xgb_ts_peak_weight    — cechy TS + waga peak

Metryki: test_mae, peak_mae (10–16), high_day_mae, case_2026-07-28 peak.

Uruchomienie:
    python scripts/train/train_time_window_peak_mlflow.py --mlflow
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

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from xgboost import XGBRegressor

from scripts.train.train_holdout_and_ts_mlflow import (
    HOLDOUT_CUT,
    PEAK_HOURS,
    CASE_DAY,
    TS_FEATURE_COLUMNS,
    add_nwp_time_series_features,
)
from scripts.train.train_hourly_model_tuning import MLFLOW_EXPERIMENT
from src.features.pv_features_hourly_extended import (
    HOURLY_FEATURE_COLUMNS_PRODUCTION,
    TARGET_COLUMN,
    load_hourly_training_frame_extended,
)
from src.models.pv_hourly_predictor import _metrics


def _xgb(weight: np.ndarray | None = None) -> tuple[Pipeline, np.ndarray | None]:
    pipe = Pipeline([
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
    return pipe, weight


def _fit_predict(pipe: Pipeline, X_tr, y_tr, X_te, sample_weight=None):
    # Pipeline nie przekazuje sample_weight do ostatniego kroku automatycznie w starszym sklearn
    # — fitujemy imputer + model ręcznie gdy są wagi.
    if sample_weight is None:
        pipe.fit(X_tr, y_tr)
        return pipe.predict(X_tr), pipe.predict(X_te), pipe

    imputer = pipe.named_steps['imputer']
    model = pipe.named_steps['model']
    X_tr_i = imputer.fit_transform(X_tr)
    X_te_i = imputer.transform(X_te)
    model.fit(X_tr_i, y_tr, sample_weight=sample_weight)
    return model.predict(X_tr_i), model.predict(X_te_i), pipe


def _evaluate(y_tr, pred_tr, y_te, pred_te, meta_te: pd.DataFrame) -> dict:
    tr = _metrics(y_tr, pred_tr)
    te = _metrics(y_te, pred_te)
    m = meta_te.copy()
    m['y_true'] = y_te.values
    m['y_pred'] = pred_te
    m['abs_err'] = (m['y_true'] - m['y_pred']).abs()
    daily_true = m.groupby('day')['y_true'].sum()
    daily_pred = m.groupby('day')['y_pred'].sum()
    peak = m[m['hour'].isin(PEAK_HOURS)]
    high_days = daily_true[daily_true >= 30].index.tolist()
    high = m[m['day'].isin(high_days)]
    case = m[(m['day'] == CASE_DAY) & (m['hour'].isin(PEAK_HOURS))]
    return {
        'train_mae': tr['mae'],
        'test_mae': te['mae'],
        'gap': te['mae'] - tr['mae'],
        'daily_mae': mean_absolute_error(daily_true, daily_pred),
        'daily_r2': r2_score(daily_true, daily_pred) if len(daily_true) > 1 else float('nan'),
        'peak_mae': float(peak['abs_err'].mean()) if len(peak) else float('nan'),
        'high_day_mae': float(high['abs_err'].mean()) if len(high) else float('nan'),
        'case_peak_mae': float(case['abs_err'].mean()) if len(case) else float('nan'),
        'n_high_days': len(high_days),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--mlflow', action='store_true')
    args = parser.parse_args()

    lat = float(os.getenv('WEATHER_LAT', '50.06'))
    lon = float(os.getenv('WEATHER_LON', '19.94'))

    print('[1] Ramka ICON + TS...')
    frame = load_hourly_training_frame_extended(
        start_date='2025-06-01', end_date='2026-07-28', latitude=lat, longitude=lon,
    )
    frame = add_nwp_time_series_features(frame)
    frame['day'] = frame['day'].astype(str)

    # dzienna suma na train — do wagi high-day
    day_sums = frame.groupby('day')[TARGET_COLUMN].sum()
    frame['day_total'] = frame['day'].map(day_sums)

    train_mask = frame['day'] < HOLDOUT_CUT
    test_mask = frame['day'] >= HOLDOUT_CUT
    meta_te = frame.loc[test_mask, ['day', 'hour']]

    base_cols = list(HOURLY_FEATURE_COLUMNS_PRODUCTION)
    ts_cols = base_cols + list(TS_FEATURE_COLUMNS)

    variants = []

    # 1) baseline
    variants.append(('tw_xgb_baseline', base_cols, None, False))

    # 2) peak weight ×3
    w_peak = np.where(frame.loc[train_mask, 'hour'].isin(PEAK_HOURS), 3.0, 1.0)
    variants.append(('tw_xgb_peak_w3', base_cols, w_peak, False))

    # 3) peak ×3 + high-day ×2 (łącznie do ×6 na peak high days)
    high_train = frame.loc[train_mask, 'day_total'] >= 30
    peak_train = frame.loc[train_mask, 'hour'].isin(PEAK_HOURS)
    w_combo = np.ones(train_mask.sum())
    w_combo = np.where(peak_train, w_combo * 3.0, w_combo)
    w_combo = np.where(high_train, w_combo * 2.0, w_combo)
    variants.append(('tw_xgb_peak_highday', base_cols, w_combo, False))

    # 4) peak-only training (osobny przedział)
    variants.append(('tw_xgb_peak_only', base_cols, None, True))

    # 5) TS + peak weight
    variants.append(('tw_xgb_ts_peak_w3', ts_cols, w_peak, False))

    results = []
    for name, cols, weights, peak_only in variants:
        tr = train_mask.copy()
        te = test_mask.copy()
        if peak_only:
            tr = tr & frame['hour'].isin(PEAK_HOURS)
            te = te & frame['hour'].isin(PEAK_HOURS)
            w = None
            meta = frame.loc[te, ['day', 'hour']]
        else:
            w = weights
            meta = meta_te

        X_tr = frame.loc[tr, cols]
        y_tr = frame.loc[tr, TARGET_COLUMN]
        X_te = frame.loc[te, cols]
        y_te = frame.loc[te, TARGET_COLUMN]

        pipe, _ = _xgb()
        print(f'\n=== {name} | cech={len(cols)} | peak_only={peak_only} ===')
        pred_tr, pred_te, pipe = _fit_predict(pipe, X_tr, y_tr, X_te, sample_weight=w)
        ev = _evaluate(y_tr, pred_tr, y_te, pred_te, meta)
        print(
            f'  holdout MAE={ev["test_mae"]:.3f} gap={ev["gap"]:.3f} '
            f'peak={ev["peak_mae"]:.3f} high_day={ev["high_day_mae"]:.3f} '
            f'{CASE_DAY}={ev["case_peak_mae"]:.3f}'
        )
        results.append({'run_name': name, **ev})

        if args.mlflow:
            import mlflow
            mlflow.set_experiment(MLFLOW_EXPERIMENT)
            with mlflow.start_run(run_name=name):
                mlflow.log_params({
                    'experiment': 'time_window_peak',
                    'split': 'chronological_holdout',
                    'holdout_cut': HOLDOUT_CUT,
                    'n_features': len(cols),
                    'peak_only': peak_only,
                    'sample_weight': 'none' if w is None else 'custom',
                    'model_type': 'xgboost',
                })
                mlflow.log_metrics({
                    'train_mae': ev['train_mae'],
                    'test_mae': ev['test_mae'],
                    'gap': ev['gap'],
                    'daily_mae': ev['daily_mae'],
                    'peak_mae': ev['peak_mae'],
                    'high_day_mae': ev['high_day_mae'],
                    'case_20260728_peak_mae': ev['case_peak_mae'],
                })
                mlflow.set_tag('experiment', 'time_window_peak')
                mlflow.set_tag('split', 'chronological_holdout')

    summary = pd.DataFrame(results).sort_values(['peak_mae', 'high_day_mae'])
    out = ROOT / 'data/processed/time_window_peak_comparison.csv'
    summary.to_csv(out, index=False)
    print('\n' + '=' * 72)
    print('PRZEDZIAŁY CZASOWE — sort peak_mae')
    print('=' * 72)
    print(summary[['run_name', 'test_mae', 'gap', 'peak_mae', 'high_day_mae', 'case_peak_mae']].to_string(index=False))
    print(f'\n✓ {out}')


if __name__ == '__main__':
    main()
