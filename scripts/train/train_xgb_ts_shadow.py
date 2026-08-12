#!/usr/bin/env python
"""
Trening XGB + TS (16 production + 8 NWP TS) → shadow joblib.

Zwycięzca walk-forward v2 — NIE nadpisuje produkcji RF 16.
Zapis: models/pv_hourly_model_xgb_ts.joblib

Uruchomienie:
    python scripts/train/train_xgb_ts_shadow.py
    python scripts/train/train_xgb_ts_shadow.py --model-path models/pv_hourly_model_xgb_ts.joblib
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

import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor

from src.features.nwp_time_series import TS_FEATURE_COLUMNS, add_nwp_time_series_features
from src.features.pv_features_hourly_extended import (
    HOURLY_FEATURE_COLUMNS_PRODUCTION,
    TARGET_COLUMN,
    load_hourly_training_frame_extended,
)
from src.models.ml_train_window import format_train_window, resolve_ml_dates
from src.models.pv_hourly_predictor import (
    TrainingReport,
    PVHourlyPredictor,
    _metrics,
    _overfit_verdict,
)

FEATURE_COLUMNS = list(HOURLY_FEATURE_COLUMNS_PRODUCTION) + list(TS_FEATURE_COLUMNS)
DEFAULT_MODEL_PATH = 'models/pv_hourly_model_xgb_ts.joblib'
SPLIT_RANDOM_STATE = 42


def _xgb_pipe() -> Pipeline:
    """Uregularyzowany XGB (min-gap) — ten sam co WF v2 / holdout TS."""
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


def main() -> None:
    parser = argparse.ArgumentParser(description='Train XGB+TS shadow model')
    parser.add_argument('--model-path', default=DEFAULT_MODEL_PATH)
    parser.add_argument('--no-save', action='store_true')
    args = parser.parse_args()

    lat = float(os.getenv('WEATHER_LAT', '50.06'))
    lon = float(os.getenv('WEATHER_LON', '19.94'))
    train_start, train_end = resolve_ml_dates()

    print('=== XGB+TS shadow train ===')
    print(f'Okno: {format_train_window(train_start, train_end)}')
    print(f'Cechy: {len(FEATURE_COLUMNS)} (production 16 + TS 8)')

    frame = load_hourly_training_frame_extended(
        start_date=train_start,
        end_date=train_end,
        latitude=lat,
        longitude=lon,
    )
    frame = add_nwp_time_series_features(frame)
    frame['day'] = frame['day'].astype(str)

    X = frame[FEATURE_COLUMNS]
    y = frame[TARGET_COLUMN]
    groups = frame['day']

    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SPLIT_RANDOM_STATE)
    train_idx, test_idx = next(gss.split(X, y, groups=groups))
    X_tr, X_te = X.iloc[train_idx], X.iloc[test_idx]
    y_tr, y_te = y.iloc[train_idx], y.iloc[test_idx]
    meta_te = frame.iloc[test_idx][['day', 'hour']].copy()

    pipe = _xgb_pipe()
    pipe.fit(X_tr, y_tr)
    pred_tr = pipe.predict(X_tr)
    pred_te = pipe.predict(X_te)
    tr = _metrics(y_tr, pred_tr)
    te = _metrics(y_te, pred_te)
    gap = te['mae'] - tr['mae']

    meta_te['y_true'] = y_te.values
    meta_te['y_pred'] = pred_te
    daily_true = meta_te.groupby('day')['y_true'].sum()
    daily_pred = meta_te.groupby('day')['y_pred'].sum()
    daily_mae = mean_absolute_error(daily_true, daily_pred)
    daily_r2 = r2_score(daily_true, daily_pred) if len(daily_true) > 1 else float('nan')

    # Refit na całym oknie treningowym (produkcyjny shadow)
    full_pipe = _xgb_pipe()
    full_pipe.fit(X, y)

    verdict = _overfit_verdict(gap, te['mae'] - tr['mae'], te['mae'])
    print(f'Train MAE: {tr["mae"]:.3f}  Test MAE: {te["mae"]:.3f}  gap={gap:.3f}')
    print(f'Daily MAE: {daily_mae:.2f}  R²={daily_r2:.3f}')
    print(verdict)

    report = TrainingReport(
        train_mae=tr['mae'],
        test_mae=te['mae'],
        gap=gap,
        cv_mae=te['mae'],
        cv_std=0.0,
        test_minus_cv=0.0,
        daily_mae=daily_mae,
        daily_r2=daily_r2,
        verdict=verdict,
        n_train=len(y_tr),
        n_test=len(y_te),
    )

    if args.no_save:
        print('Pominięto zapis (--no-save)')
        return

    predictor = PVHourlyPredictor(model_path=args.model_path)
    predictor.feature_columns = list(FEATURE_COLUMNS)
    predictor.pipeline = full_pipe
    predictor.latitude = lat
    predictor.longitude = lon
    predictor.location = os.getenv('WEATHER_LOCATION')
    predictor.report = report
    path = predictor.save()
    print(f'✓ Shadow XGB+TS → {path}')


if __name__ == '__main__':
    main()
