#!/usr/bin/env python
"""
Trening XGB + TS (16 production + 8 NWP TS) → shadow joblib.

Zwycięzca walk-forward v2 — NIE nadpisuje produkcji RF 16.
Zapis: models/pv_hourly_model_xgb_ts.joblib

Dual report: shuffle Test MAE + chronological L30 (soft gate, bez REJECT).
Prod fit: pełne expanding do train_end (jak dotychczas).

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
from src.models.weekly_dual_metrics import (
    append_dual_history,
    chronological_l30_masks,
    evaluate_holdout_pipeline,
    load_prev_shuffle_mae,
    print_dual_report,
    shuffle_gate_vs_prev,
    soft_gate_l30,
)

FEATURE_COLUMNS = list(HOURLY_FEATURE_COLUMNS_PRODUCTION) + list(TS_FEATURE_COLUMNS)
DEFAULT_MODEL_PATH = 'models/pv_hourly_model_xgb_ts.joblib'
SPLIT_RANDOM_STATE = 42
FEATURE_SET = 'xgb_ts'


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
    print('Dual: shuffle 80/20 + L30 | prod fit=full expanding')

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

    chrono_tr, chrono_te, hold_start, hold_end = chronological_l30_masks(
        frame['day'], train_end,
    )
    l30 = evaluate_holdout_pipeline(
        _xgb_pipe(),
        frame,
        FEATURE_COLUMNS,
        TARGET_COLUMN,
        chrono_tr,
        chrono_te,
    )
    soft = soft_gate_l30(l30.get('test_mae'))
    prev_shuf = load_prev_shuffle_mae(FEATURE_SET)
    shuf_gate = shuffle_gate_vs_prev(te['mae'], prev_shuf)
    print_dual_report(
        feature_set=FEATURE_SET,
        shuffle_mae=te['mae'],
        shuffle_daily_mae=daily_mae,
        l30=l30,
        hold_start=hold_start,
        hold_end=hold_end,
        soft=soft,
        shuffle_gate=shuf_gate,
    )

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

    hist_path = append_dual_history({
        'feature_set': FEATURE_SET,
        'train_start': train_start,
        'train_end': train_end,
        'shuffle_test_mae': te['mae'],
        'shuffle_daily_mae': daily_mae,
        'l30_test_mae': l30.get('test_mae'),
        'l30_daily_mae': l30.get('daily_mae'),
        'l30_hold_start': hold_start,
        'l30_hold_end': hold_end,
        'soft_gate_l30': soft['status'],
        'shuffle_gate': shuf_gate['status'],
        'shuffle_gate_delta': shuf_gate.get('delta'),
        'model_path': args.model_path,
    })
    print(f'✓ dual history → {hist_path}')

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
    path = predictor.save(extra_metadata={
        'feature_set': FEATURE_SET,
        'train_start': train_start,
        'train_end': train_end,
        'prod_fit': 'full_expanding_window',
        'dual_report': {
            'shuffle_test_mae': te['mae'],
            'shuffle_daily_mae': daily_mae,
            'l30_test_mae': l30.get('test_mae'),
            'l30_daily_mae': l30.get('daily_mae'),
            'l30_hold_start': hold_start,
            'l30_hold_end': hold_end,
            'soft_gate_l30': soft,
            'shuffle_gate': shuf_gate,
        },
    })
    print(f'✓ Shadow XGB+TS → {path}')


if __name__ == '__main__':
    main()
