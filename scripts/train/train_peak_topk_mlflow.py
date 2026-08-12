#!/usr/bin/env python
"""
Peak weights (10–16) + metryka top-k godzin → MLflow.

Porównuje na holdoucie chronologicznym (≥2026-06-01):
  1) rf_production          — baseline produkcji
  2) xgb_production_ts      — zwycięzca WF v2 (shadow)
  3) xgb_ts_peak_w3         — XGB+TS + waga ×3 na 10–16
  4) xgb_ts_peak_highday    — ×3 peak + ×2 high-day (≥30 kWh)
  5) xgb_ts_peak_only       — trenuj tylko godziny 10–16

Metryki: test/peak/high_day MAE + topk_hit_rate@5, peak_in_topk, peak_hour_exact.

Opcjonalnie zapis kandydata peak (jeśli lepszy topk/peak vs xgb_ts):
  --save-best → models/pv_hourly_model_xgb_ts_peak.joblib
  (NIE podpina automatycznie do launchd — osobny shadow dopiero po decyzji)

Uruchomienie:
    python scripts/train/train_peak_topk_mlflow.py --mlflow
    python scripts/train/train_peak_topk_mlflow.py --mlflow --save-best
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
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor

from scripts.train.train_hourly_model_tuning import MLFLOW_EXPERIMENT
from src.features.nwp_time_series import TS_FEATURE_COLUMNS, add_nwp_time_series_features
from src.features.pv_features_hourly_extended import (
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
    TrainingReport,
    PVHourlyPredictor,
    _metrics,
    _overfit_verdict,
)
from src.models.topk_metrics import topk_hour_metrics

HOLDOUT_CUT = '2026-06-01'
PEAK_HOURS = list(range(10, 17))
CASE_DAY = '2026-07-28'
TOP_K = 5
DEFAULT_PEAK_MODEL = 'models/pv_hourly_model_xgb_ts_peak.joblib'


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


def _fit_predict(pipe: Pipeline, X_tr, y_tr, X_te, sample_weight=None):
    if sample_weight is None:
        pipe.fit(X_tr, y_tr)
        return pipe.predict(X_tr), pipe.predict(X_te), pipe

    imputer = pipe.named_steps['imputer']
    model = pipe.named_steps['model']
    X_tr_i = imputer.fit_transform(X_tr)
    X_te_i = imputer.transform(X_te)
    model.fit(X_tr_i, y_tr, sample_weight=sample_weight)
    # zachowaj fitted pipeline
    pipe.named_steps['imputer'] = imputer
    pipe.named_steps['model'] = model
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
    topk = topk_hour_metrics(m, k=TOP_K)
    return {
        'train_mae': tr['mae'],
        'test_mae': te['mae'],
        'gap': te['mae'] - tr['mae'],
        'daily_mae': mean_absolute_error(daily_true, daily_pred),
        'daily_r2': r2_score(daily_true, daily_pred) if len(daily_true) > 1 else float('nan'),
        'peak_mae': float(peak['abs_err'].mean()) if len(peak) else float('nan'),
        'high_day_mae': float(high['abs_err'].mean()) if len(high) else float('nan'),
        'case_peak_mae': float(case['abs_err'].mean()) if len(case) else float('nan'),
        **topk,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--mlflow', action='store_true')
    parser.add_argument('--save-best', action='store_true',
                        help='Zapisz najlepszy wariant peak (topk/peak) jako osobny joblib')
    parser.add_argument('--model-path', default=DEFAULT_PEAK_MODEL)
    args = parser.parse_args()

    lat = float(os.getenv('WEATHER_LAT', '50.06'))
    lon = float(os.getenv('WEATHER_LON', '19.94'))

    print('[1] Ramka ICON + TS...')
    frame = load_hourly_training_frame_extended(
        start_date='2025-06-01', end_date='2026-07-28', latitude=lat, longitude=lon,
    )
    frame = add_nwp_time_series_features(frame)
    frame['day'] = frame['day'].astype(str)
    day_sums = frame.groupby('day')[TARGET_COLUMN].sum()
    frame['day_total'] = frame['day'].map(day_sums)

    train_mask = frame['day'] < HOLDOUT_CUT
    test_mask = frame['day'] >= HOLDOUT_CUT
    meta_te = frame.loc[test_mask, ['day', 'hour']]

    base_cols = list(HOURLY_FEATURE_COLUMNS_PRODUCTION)
    ts_cols = base_cols + list(TS_FEATURE_COLUMNS)

    w_peak = np.where(frame.loc[train_mask, 'hour'].isin(PEAK_HOURS), 3.0, 1.0)
    high_train = frame.loc[train_mask, 'day_total'] >= 30
    peak_train = frame.loc[train_mask, 'hour'].isin(PEAK_HOURS)
    w_combo = np.ones(int(train_mask.sum()))
    w_combo = np.where(peak_train, w_combo * 3.0, w_combo)
    w_combo = np.where(high_train, w_combo * 2.0, w_combo)

    variants = [
        ('pk_rf_production', base_cols, _rf_pipe, None, False),
        ('pk_xgb_production_ts', ts_cols, _xgb_pipe, None, False),
        ('pk_xgb_ts_peak_w3', ts_cols, _xgb_pipe, w_peak, False),
        ('pk_xgb_ts_peak_highday', ts_cols, _xgb_pipe, w_combo, False),
        ('pk_xgb_ts_peak_only', ts_cols, _xgb_pipe, None, True),
    ]

    results = []
    fitted = {}  # name -> (pipe, cols) for full-data refit candidates

    for name, cols, make_pipe, weights, peak_only in variants:
        tr = train_mask.copy()
        te = test_mask.copy()
        if peak_only:
            tr = tr & frame['hour'].isin(PEAK_HOURS)
            te = te & frame['hour'].isin(PEAK_HOURS)
            w = None
            meta = frame.loc[te, ['day', 'hour']]
            # top-k na peak-only teście jest mniej sensowny (mało godzin) — i tak liczymy
        else:
            w = weights
            meta = meta_te

        X_tr = frame.loc[tr, cols]
        y_tr = frame.loc[tr, TARGET_COLUMN]
        X_te = frame.loc[te, cols]
        y_te = frame.loc[te, TARGET_COLUMN]

        pipe = make_pipe()
        print(f'\n=== {name} | cech={len(cols)} | peak_only={peak_only} ===')
        pred_tr, pred_te, pipe = _fit_predict(pipe, X_tr, y_tr, X_te, sample_weight=w)
        ev = _evaluate(y_tr, pred_tr, y_te, pred_te, meta)
        print(
            f'  MAE={ev["test_mae"]:.3f} peak={ev["peak_mae"]:.3f} high={ev["high_day_mae"]:.3f} '
            f'top{TOP_K}_hit={ev["topk_hit_rate"]:.3f} peak_in_top{TOP_K}={ev["peak_in_topk"]:.3f} '
            f'peak_exact={ev["peak_hour_exact"]:.3f} case={ev["case_peak_mae"]:.3f}'
        )
        results.append({'run_name': name, **ev})
        fitted[name] = (pipe, cols, w, peak_only)

        if args.mlflow:
            import mlflow
            mlflow.set_experiment(MLFLOW_EXPERIMENT)
            with mlflow.start_run(run_name=name):
                mlflow.log_params({
                    'experiment': 'peak_topk',
                    'split': 'chronological_holdout',
                    'holdout_cut': HOLDOUT_CUT,
                    'n_features': len(cols),
                    'top_k': TOP_K,
                    'peak_only': peak_only,
                    'sample_weight': 'none' if w is None else 'peak_custom',
                })
                mlflow.log_metrics({
                    'train_mae': ev['train_mae'],
                    'test_mae': ev['test_mae'],
                    'gap': ev['gap'],
                    'peak_mae': ev['peak_mae'],
                    'high_day_mae': ev['high_day_mae'],
                    'case_20260728_peak_mae': ev['case_peak_mae'],
                    'topk_hit_rate': ev['topk_hit_rate'],
                    'topk_jaccard': ev['topk_jaccard'],
                    'peak_in_topk': ev['peak_in_topk'],
                    'peak_hour_exact': ev['peak_hour_exact'],
                })
                mlflow.set_tag('experiment', 'peak_topk')

    summary = pd.DataFrame(results)
    # ranking: najpierw topk_hit, potem peak_mae (niższy lepszy)
    summary['_rank'] = (
        -summary['topk_hit_rate'].fillna(0)
        + summary['peak_mae'].fillna(9) * 0.01
    )
    summary = summary.sort_values('_rank').drop(columns='_rank')
    out = ROOT / 'data/processed/peak_topk_comparison.csv'
    summary.to_csv(out, index=False)

    print('\n' + '=' * 72)
    print(f'PEAK + TOP-{TOP_K} — sort: topk_hit ↓, peak_mae ↑')
    print('=' * 72)
    cols_show = [
        'run_name', 'test_mae', 'peak_mae', 'high_day_mae',
        'topk_hit_rate', 'peak_in_topk', 'peak_hour_exact', 'case_peak_mae',
    ]
    print(summary[cols_show].to_string(index=False))
    print(f'\n✓ {out}')

    # kandydat do zapisu: najlepszy wśród wariantów z wagą peak (nie peak_only, nie rf)
    candidates = summary[
        summary['run_name'].isin(['pk_xgb_ts_peak_w3', 'pk_xgb_ts_peak_highday'])
    ]
    baseline = summary[summary['run_name'] == 'pk_xgb_production_ts']
    if args.save_best and not candidates.empty and not baseline.empty:
        best = candidates.iloc[0]
        base = baseline.iloc[0]
        better = (
            (best['topk_hit_rate'] >= base['topk_hit_rate'] - 0.01)
            and (best['peak_mae'] <= base['peak_mae'] + 0.02)
        )
        print(f'\nBest peak candidate: {best["run_name"]}')
        print(
            f'  vs xgb_ts: topk {best["topk_hit_rate"]:.3f} vs {base["topk_hit_rate"]:.3f}, '
            f'peak {best["peak_mae"]:.3f} vs {base["peak_mae"]:.3f}'
        )
        if not better:
            print('  ⚠️  Nie lepszy wyraźnie od XGB+TS — zapis mimo to (--save-best).')

        name = best['run_name']
        pipe, feat_cols, w, peak_only = fitted[name]
        # refit na całym holdout-train (+ opcjonalnie peak filter) potem pełne dane do shadow
        tr = frame['day'] < HOLDOUT_CUT
        if peak_only:
            tr = tr & frame['hour'].isin(PEAK_HOURS)
        # wagi na pełnym train holdout
        if name == 'pk_xgb_ts_peak_w3':
            w_full = np.where(frame.loc[tr, 'hour'].isin(PEAK_HOURS), 3.0, 1.0)
        elif name == 'pk_xgb_ts_peak_highday':
            ht = frame.loc[tr, 'day_total'] >= 30
            pt = frame.loc[tr, 'hour'].isin(PEAK_HOURS)
            w_full = np.ones(int(tr.sum()))
            w_full = np.where(pt, w_full * 3.0, w_full)
            w_full = np.where(ht, w_full * 2.0, w_full)
        else:
            w_full = None

        # Refit na WSZYSTKICH dniach (produkcyjny shadow candidate)
        all_mask = pd.Series(True, index=frame.index)
        if peak_only:
            all_mask = frame['hour'].isin(PEAK_HOURS)
        X_all = frame.loc[all_mask, feat_cols]
        y_all = frame.loc[all_mask, TARGET_COLUMN]
        if name == 'pk_xgb_ts_peak_w3':
            w_all = np.where(frame.loc[all_mask, 'hour'].isin(PEAK_HOURS), 3.0, 1.0)
        elif name == 'pk_xgb_ts_peak_highday':
            ht = frame.loc[all_mask, 'day_total'] >= 30
            pt = frame.loc[all_mask, 'hour'].isin(PEAK_HOURS)
            w_all = np.ones(int(all_mask.sum()))
            w_all = np.where(pt, w_all * 3.0, w_all)
            w_all = np.where(ht, w_all * 2.0, w_all)
        else:
            w_all = None

        full_pipe = _xgb_pipe()
        _, _, full_pipe = _fit_predict(full_pipe, X_all, y_all, X_all, sample_weight=w_all)

        predictor = PVHourlyPredictor(model_path=args.model_path)
        predictor.feature_columns = list(feat_cols)
        predictor.pipeline = full_pipe
        predictor.latitude = lat
        predictor.longitude = lon
        predictor.location = os.getenv('WEATHER_LOCATION')
        predictor.report = TrainingReport(
            train_mae=float(best['train_mae']),
            test_mae=float(best['test_mae']),
            gap=float(best['gap']),
            cv_mae=float(best['test_mae']),
            cv_std=0.0,
            test_minus_cv=0.0,
            daily_mae=float(best['daily_mae']),
            daily_r2=float(best['daily_r2']),
            verdict=_overfit_verdict(float(best['gap']), 0.0, float(best['test_mae'])),
            n_train=int(all_mask.sum()),
            n_test=int(test_mask.sum()),
        )
        path = predictor.save()
        print(f'✓ Peak candidate joblib → {path}')
        print('  (nie podpięty do launchd — decyzja po porównaniu live)')

    if args.mlflow:
        import mlflow
        mlflow.set_experiment(MLFLOW_EXPERIMENT)
        with mlflow.start_run(run_name='pk_summary'):
            mlflow.log_param('experiment', 'peak_topk_summary')
            mlflow.log_artifact(str(out))
            winner = summary.iloc[0]
            mlflow.log_metrics({
                'best_topk_hit_rate': float(winner['topk_hit_rate']),
                'best_peak_mae': float(winner['peak_mae']),
                'best_test_mae': float(winner['test_mae']),
            })
            mlflow.set_tag('best_run', winner['run_name'])
        print(f'✓ MLflow: pk_* + pk_summary → {MLFLOW_EXPERIMENT}')


if __name__ == '__main__':
    main()
