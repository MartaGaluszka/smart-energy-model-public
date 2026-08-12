#!/usr/bin/env python
"""
Ten sam split/metodyka co train_hourly_model_tuning.py, ale z XGBoost zamiast RF —
druga "oś" eksperymentu w MLflow (nie tylko zestaw cech, ale i typ modelu).

Wykorzystuje ZAPISANY split z features_16_vs_19_split.json (ten sam co RF), więc
wyniki są bezpośrednio porównywalne 1:1 z runami "production"/"cs4"/"panel"/"cs4_panel"
w eksperymencie MLflow "pv-hourly-forecast".

Uruchomienie:
    python scripts/train/train_hourly_model_tuning.py --features panel  # najpierw, zapisuje split
    python scripts/train/train_hourly_model_xgboost.py --features panel --mlflow
"""

from __future__ import annotations

import argparse
import json
import os

import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv()

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor

from scripts.train.train_hourly_model_tuning import (
    CV_TOLERANCE,
    FEATURE_SETS,
    MLFLOW_EXPERIMENT,
    SPLIT_RANDOM_STATE,
    COMPARE_SPLIT_JSON,
)
from src.features.pv_features_hourly_extended import TARGET_COLUMN, load_hourly_training_frame_extended
from src.models.ml_train_window import format_train_window, resolve_train_window
from src.models.pv_hourly_predictor import _metrics, _overfit_verdict

XGB_PARAM_GRID = {
    'model__max_depth': [3, 4, 5, 6],
    'model__learning_rate': [0.05, 0.1],
    'model__subsample': [0.8, 1.0],
    'model__colsample_bytree': [0.8, 1.0],
    'model__n_estimators': [200],
    'model__min_child_weight': [5, 10],
}


def _make_pipeline() -> Pipeline:
    return Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('model', XGBRegressor(random_state=42, n_jobs=-1, objective='reg:absoluteerror')),
    ])


def _extract_params(pipeline: Pipeline) -> dict:
    m = pipeline.named_steps['model']
    return {
        'n_estimators': m.n_estimators,
        'max_depth': m.max_depth,
        'learning_rate': m.learning_rate,
        'subsample': m.subsample,
        'colsample_bytree': m.colsample_bytree,
        'min_child_weight': m.min_child_weight,
    }


def _evaluate_candidate(params, X_train, y_train, X_test, y_test, meta_test) -> dict:
    pipe = _make_pipeline()
    pipe.set_params(**params)
    pipe.fit(X_train, y_train)

    train_pred = pipe.predict(X_train)
    test_pred = pipe.predict(X_test)
    train_m = _metrics(y_train, train_pred)
    test_m = _metrics(y_test, test_pred)
    gap = test_m['mae'] - train_m['mae']

    test_with_pred = meta_test.copy()
    test_with_pred['y_true'] = y_test.values
    test_with_pred['y_pred'] = test_pred
    daily_true = test_with_pred.groupby('day')['y_true'].sum()
    daily_pred = test_with_pred.groupby('day')['y_pred'].sum()
    daily_mae = mean_absolute_error(daily_true, daily_pred)
    daily_r2 = r2_score(daily_true, daily_pred)

    return {
        'pipeline': pipe, 'params': params,
        'train_mae': train_m['mae'], 'train_r2': train_m['r2'],
        'test_mae': test_m['mae'], 'test_r2': test_m['r2'],
        'gap': gap, 'daily_mae': daily_mae, 'daily_r2': daily_r2,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='XGBoost — ta sama metodyka/split co RF tuning')
    parser.add_argument('--features', choices=sorted(FEATURE_SETS), default='panel')
    parser.add_argument('--mlflow', action='store_true')
    args = parser.parse_args()

    train_start, train_end = resolve_train_window(train_start=None, train_end=None)
    print(f'Okno treningowe: {format_train_window(train_start, train_end)}')

    frame = load_hourly_training_frame_extended(
        start_date=train_start, end_date=train_end, latitude=50.06, longitude=19.94,
    )
    frame['day'] = frame['day'].astype(str)

    with open(COMPARE_SPLIT_JSON, encoding='utf-8') as f:
        split_meta = json.load(f)
    train_days = set(split_meta['train_days'])
    test_days = set(split_meta['test_days'])
    train_mask = frame['day'].isin(train_days)
    test_mask = frame['day'].isin(test_days)
    print(f'✓ Split wczytany z {COMPARE_SPLIT_JSON} (ten sam co RF) — '
          f'{len(train_days)} dni train / {len(test_days)} dni test')

    spec = FEATURE_SETS[args.features]
    feature_columns = spec['columns']
    print(f'Zestaw cech: {args.features} ({spec["label"]}, {len(feature_columns)} cech)')

    X_train = frame.loc[train_mask, feature_columns]
    y_train = frame.loc[train_mask, TARGET_COLUMN]
    X_test = frame.loc[test_mask, feature_columns]
    y_test = frame.loc[test_mask, TARGET_COLUMN]
    groups = frame.loc[train_mask, 'day']
    meta_test = frame.loc[test_mask, ['day', 'hour']]

    n_combos = int(np.prod([len(v) for v in XGB_PARAM_GRID.values()]))
    print(f'\n[2] GridSearchCV XGBoost ({n_combos} kombinacji × GroupKFold(n=5))...')
    gkf = GroupKFold(n_splits=5)
    grid = GridSearchCV(
        estimator=_make_pipeline(), param_grid=XGB_PARAM_GRID, cv=gkf,
        scoring='neg_mean_absolute_error', refit=False, n_jobs=-1, verbose=0,
    )
    grid.fit(X_train, y_train, groups=groups)

    cv_results = pd.DataFrame(grid.cv_results_)
    cv_results['cv_mae'] = -cv_results['mean_test_score']
    best_cv_mae = cv_results['cv_mae'].min()
    cv_threshold = best_cv_mae * (1 + CV_TOLERANCE)
    shortlist_idx = cv_results.index[cv_results['cv_mae'] <= cv_threshold].tolist()
    print(f'   Najlepsze CV MAE: {best_cv_mae:.3f} kWh/h | kandydaci w tolerancji: {len(shortlist_idx)}/{len(cv_results)}')

    print('\n[3] Ocena kandydatów (wybór min gap)...')
    candidates = []
    for idx in shortlist_idx:
        params = grid.cv_results_['params'][idx]
        ev = _evaluate_candidate(params, X_train, y_train, X_test, y_test, meta_test)
        ev['cv_mae'] = cv_results.loc[idx, 'cv_mae']
        candidates.append(ev)
    candidates.sort(key=lambda c: (c['gap'], c['test_mae']))
    best = candidates[0]

    print('\n[4] Wybrany model XGBoost (najmniejszy gap):')
    p = _extract_params(best['pipeline'])
    print(f'   {p}')
    print(f'   Train MAE: {best["train_mae"]:.3f} | Test MAE: {best["test_mae"]:.3f} | Gap: {best["gap"]:.3f}')
    print(f'   Dzienny MAE: {best["daily_mae"]:.3f} kWh/dzień, R²={best["daily_r2"]:.3f}')

    print('\n[5] Cross-validation wybranego modelu...')
    cv_scores = []
    for fold, (tr, va) in enumerate(gkf.split(X_train, y_train, groups=groups), 1):
        fold_pipe = _make_pipeline()
        fold_pipe.set_params(**best['params'])
        fold_pipe.fit(X_train.iloc[tr], y_train.iloc[tr])
        val_pred = fold_pipe.predict(X_train.iloc[va])
        mae = mean_absolute_error(y_train.iloc[va], val_pred)
        cv_scores.append(mae)
    cv_mean = float(np.mean(cv_scores))
    cv_std = float(np.std(cv_scores))
    test_minus_cv = best['test_mae'] - cv_mean
    verdict = _overfit_verdict(best['gap'], test_minus_cv, best['test_mae'])
    print(f'   CV: {cv_mean:.3f} ± {cv_std:.3f} kWh/h | {verdict}')

    run_name = f'xgboost_{args.features}'
    if args.mlflow:
        import mlflow
        import mlflow.sklearn

        mlflow.set_experiment(MLFLOW_EXPERIMENT)
        with mlflow.start_run(run_name=run_name):
            mlflow.log_params({
                'feature_set': args.features,
                'feature_set_label': spec['label'],
                'n_features': len(feature_columns),
                'model_type': 'xgboost',
                'train_start': train_start,
                'train_end': train_end,
                'split_random_state': SPLIT_RANDOM_STATE,
                **{f'xgb_{k}': v for k, v in p.items()},
            })
            mlflow.log_metrics({
                'train_mae': best['train_mae'], 'train_r2': best['train_r2'],
                'test_mae': best['test_mae'], 'test_r2': best['test_r2'],
                'gap': best['gap'], 'cv_mae': cv_mean, 'cv_std': cv_std,
                'daily_mae': best['daily_mae'], 'daily_r2': best['daily_r2'],
            })
            mlflow.set_tag('verdict', verdict)
            mlflow.set_tag('model_type', 'xgboost')
            mlflow.sklearn.log_model(best['pipeline'], name='model')
        print(f'\n✓ Zalogowano run "{run_name}" (model_type=xgboost) do "{MLFLOW_EXPERIMENT}"')


if __name__ == '__main__':
    main()
