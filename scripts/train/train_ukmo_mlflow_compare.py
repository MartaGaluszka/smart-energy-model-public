#!/usr/bin/env python
"""
Porównanie MLflow: pogoda UKMO (zamiast ICON z DB) × 3 zestawy cech × RF/XGBoost.

Zestawy cech (jak ustalono):
  1) cs4        — 19 cech (warstwy chmur + clearness)
  2) panel      — 16 + geometria dachu
  3) cs4_panel  — CS4 + geometria dachu

Ten sam split co dotychczasowe runy ICON (features_16_vs_19_split.json).
NIE zmienia OPENMETEO_MODEL / produkcji / weather_data w DB.

Uruchomienie:
    PANEL_GEOMETRY_FEATURES=1 python scripts/train/train_ukmo_mlflow_compare.py --mlflow
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')

os.environ.setdefault('PANEL_GEOMETRY_FEATURES', '1')
os.environ.setdefault('MPLCONFIGDIR', '/tmp/mpl')
os.environ.setdefault('MPLBACKEND', 'Agg')

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor

from scripts.train.train_hourly_model_tuning import (
    COMPARE_SPLIT_JSON,
    CV_TOLERANCE,
    FEATURE_SETS,
    MLFLOW_EXPERIMENT,
    PARAM_GRID,
    SPLIT_RANDOM_STATE,
)
from src.data.weather_api import OpenMeteoClient
from src.features.clearness import add_clearness_features
from src.features.panel_geometry import add_panel_geometry_features
from src.features.pv_features_hourly_extended import (
    TARGET_COLUMN,
    calculate_sun_features,
    load_hourly_pv_dynamic,
)
from src.models.ml_train_window import format_train_window, resolve_train_window
from src.models.pv_hourly_predictor import _metrics, _overfit_verdict

UKMO_CACHE = ROOT / 'data/processed/ukmo_archive_hourly_cache.csv'
CASES = ('cs4', 'panel', 'cs4_panel')

XGB_PARAM_GRID = {
    'model__max_depth': [3, 4, 5, 6],
    'model__learning_rate': [0.05, 0.1],
    'model__subsample': [0.8, 1.0],
    'model__colsample_bytree': [0.8, 1.0],
    'model__n_estimators': [200],
    'model__min_child_weight': [5, 10],
}


def _fetch_or_load_ukmo(start: str, end: str, lat: float, lon: float) -> pd.DataFrame:
    if UKMO_CACHE.exists():
        cached = pd.read_csv(UKMO_CACHE)
        cached['timestamp'] = pd.to_datetime(cached['timestamp'])
        c_min = cached['timestamp'].min().date().isoformat()
        c_max = cached['timestamp'].max().date().isoformat()
        if c_min <= start and c_max >= end:
            print(f'✓ UKMO z cache: {UKMO_CACHE} ({c_min}–{c_max}, {len(cached)} h)')
            return cached

    print(f'[fetch] ukmo_seamless archive {start} → {end}...')
    client = OpenMeteoClient(lat, lon, location_label='home', model='ukmo_seamless')
    raw = client.fetch_archive(start, end, chunk_days=31)
    if raw.empty:
        raise RuntimeError('Puste archiwum UKMO z Open-Meteo')
    UKMO_CACHE.parent.mkdir(parents=True, exist_ok=True)
    raw.to_csv(UKMO_CACHE, index=False)
    print(f'✓ Zapisano cache: {UKMO_CACHE} ({len(raw)} h)')
    return raw


def _ukmo_to_hourly(raw: pd.DataFrame) -> pd.DataFrame:
    out = raw.copy()
    out['timestamp'] = pd.to_datetime(out['timestamp'])
    out['day'] = out['timestamp'].dt.strftime('%Y-%m-%d')
    out['hour'] = out['timestamp'].dt.hour.astype(int)
    hourly = (
        out.groupby(['day', 'hour'], as_index=False)
        .agg(
            temp_c=('temperature_celsius', 'mean'),
            humidity_pct=('humidity_percent', 'mean'),
            cloud_cover_pct=('cloud_cover_percent', 'mean'),
            cloud_cover_low_pct=('cloud_cover_low_percent', 'mean'),
            cloud_cover_mid_pct=('cloud_cover_mid_percent', 'mean'),
            radiation_wm2=('solar_radiation_wm2', 'mean'),
            wind_speed_ms=('wind_speed_ms', 'mean'),
            snow_depth_m=('snow_depth_m', 'mean'),
        )
    )
    hourly['cloud_cover_low_pct'] = hourly['cloud_cover_low_pct'].fillna(hourly['cloud_cover_pct'])
    hourly['cloud_cover_mid_pct'] = hourly['cloud_cover_mid_pct'].fillna(hourly['cloud_cover_pct'])
    return hourly


def build_ukmo_training_frame(start: str, end: str, lat: float, lon: float) -> pd.DataFrame:
    """PV z DB + pogoda UKMO (nie ICON) + cechy słoneczne / clearness / geometria."""
    db_path = os.getenv('DATABASE_PATH', str(ROOT / 'data/energy_model.db'))
    if not os.path.isabs(db_path):
        db_path = str(ROOT / db_path)

    print('\n[1] PV z bazy + pogoda UKMO...')
    pv = load_hourly_pv_dynamic(db_path, start, end, min_hour=5, max_hour=21)
    raw = _fetch_or_load_ukmo(start, end, lat, lon)
    weather = _ukmo_to_hourly(raw)
    weather = weather[(weather['hour'] >= 5) & (weather['hour'] <= 21)]

    df = pv.merge(weather, on=['day', 'hour'], how='inner')
    print(f'   po merge PV∩UKMO: {len(df)} h, {df["day"].nunique()} dni')

    df = calculate_sun_features(df, latitude=lat, longitude=lon)
    df = add_clearness_features(df, latitude=lat, longitude=lon)
    df = add_panel_geometry_features(df, latitude=lat, longitude=lon)
    print('✓ Cechy: słońce + clearness + geometria paneli')

    # Proste flagi śniegu z UKMO (bez melt modelu ICON-DB)
    daily_snow = (
        weather.groupby('day', as_index=False)['snow_depth_m']
        .max()
        .rename(columns={'snow_depth_m': 'snow_depth_m_max'})
    )
    daily_snow['snow_on_panels'] = (daily_snow['snow_depth_m_max'].fillna(0) > 0.05).astype(int)
    daily_snow = daily_snow.sort_values('day')
    daily_snow['snow_on_panels_prev'] = daily_snow['snow_on_panels'].shift(1).fillna(0).astype(int)
    df = df.merge(daily_snow[['day', 'snow_on_panels', 'snow_on_panels_prev']], on='day', how='left')
    df['snow_on_panels'] = df['snow_on_panels'].fillna(0).astype(int)
    df['snow_on_panels_prev'] = df['snow_on_panels_prev'].fillna(0).astype(int)
    df['likely_fog_day'] = 0  # bez osobnej kalibracji na UKMO

    dt = pd.to_datetime(df['day'])
    doy = dt.dt.dayofyear
    df['doy_sin'] = np.sin(2 * np.pi * doy / 365.25)
    df['doy_cos'] = np.cos(2 * np.pi * doy / 365.25)
    df['month'] = dt.dt.month

    valid = (
        df[TARGET_COLUMN].notna()
        & df['radiation_wm2'].notna()
        & (df['is_daylight'] == 1)
        & (df[TARGET_COLUMN] > 0.01)
    )
    df = df.loc[valid].copy().reset_index(drop=True)
    print(f'✓ Ramka UKMO: {len(df)} h daylight, {df["day"].nunique()} dni')
    return df


def _make_rf() -> Pipeline:
    return Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('model', RandomForestRegressor(random_state=42, n_jobs=-1)),
    ])


def _make_xgb() -> Pipeline:
    return Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('model', XGBRegressor(random_state=42, n_jobs=-1, objective='reg:absoluteerror')),
    ])


def _evaluate(pipe, X_train, y_train, X_test, y_test, meta_test) -> dict:
    train_pred = pipe.predict(X_train)
    test_pred = pipe.predict(X_test)
    train_m = _metrics(y_train, train_pred)
    test_m = _metrics(y_test, test_pred)
    gap = test_m['mae'] - train_m['mae']
    tw = meta_test.copy()
    tw['y_true'] = y_test.values
    tw['y_pred'] = test_pred
    daily_true = tw.groupby('day')['y_true'].sum()
    daily_pred = tw.groupby('day')['y_pred'].sum()
    return {
        'pipeline': pipe,
        'train_mae': train_m['mae'],
        'train_r2': train_m['r2'],
        'test_mae': test_m['mae'],
        'test_r2': test_m['r2'],
        'gap': gap,
        'daily_mae': mean_absolute_error(daily_true, daily_pred),
        'daily_r2': r2_score(daily_true, daily_pred),
    }


def run_one(
    *,
    model_type: str,
    feature_key: str,
    frame: pd.DataFrame,
    train_mask,
    test_mask,
    train_start: str,
    train_end: str,
    log_mlflow: bool,
) -> dict:
    spec = FEATURE_SETS[feature_key]
    cols = list(spec['columns'])
    missing = [c for c in cols if c not in frame.columns]
    if missing:
        raise KeyError(f'Brak kolumn {missing} w ramce UKMO')

    X_train = frame.loc[train_mask, cols]
    y_train = frame.loc[train_mask, TARGET_COLUMN]
    X_test = frame.loc[test_mask, cols]
    y_test = frame.loc[test_mask, TARGET_COLUMN]
    groups = frame.loc[train_mask, 'day']
    meta_test = frame.loc[test_mask, ['day', 'hour']]

    if model_type == 'rf':
        estimator = _make_rf()
        param_grid = PARAM_GRID
        param_prefix = 'rf_'
    else:
        estimator = _make_xgb()
        param_grid = XGB_PARAM_GRID
        param_prefix = 'xgb_'

    run_name = f'ukmo_{model_type}_{feature_key}'
    n_combos = int(np.prod([len(v) for v in param_grid.values()]))
    print('\n' + '=' * 72)
    print(f'{run_name} | {spec["label"]} | {len(cols)} cech | siatka {n_combos}')
    print('=' * 72)

    gkf = GroupKFold(n_splits=5)
    grid = GridSearchCV(
        estimator=estimator,
        param_grid=param_grid,
        cv=gkf,
        scoring='neg_mean_absolute_error',
        refit=False,
        n_jobs=-1,
        verbose=0,
    )
    grid.fit(X_train, y_train, groups=groups)

    cv_results = pd.DataFrame(grid.cv_results_)
    cv_results['cv_mae'] = -cv_results['mean_test_score']
    best_cv = cv_results['cv_mae'].min()
    threshold = best_cv * (1 + CV_TOLERANCE)
    shortlist = cv_results.index[cv_results['cv_mae'] <= threshold].tolist()

    candidates = []
    for idx in shortlist:
        params = grid.cv_results_['params'][idx]
        pipe = clone(estimator)
        pipe.set_params(**params)
        pipe.fit(X_train, y_train)
        ev = _evaluate(pipe, X_train, y_train, X_test, y_test, meta_test)
        ev['cv_mae_grid'] = float(cv_results.loc[idx, 'cv_mae'])
        ev['params'] = params
        candidates.append(ev)
    candidates.sort(key=lambda c: (c['gap'], c['test_mae']))
    best = candidates[0]

    cv_scores = []
    for tr, va in gkf.split(X_train, y_train, groups=groups):
        fold = clone(best['pipeline'])
        fold.fit(X_train.iloc[tr], y_train.iloc[tr])
        cv_scores.append(mean_absolute_error(y_train.iloc[va], fold.predict(X_train.iloc[va])))
    cv_mean = float(np.mean(cv_scores))
    cv_std = float(np.std(cv_scores))
    verdict = _overfit_verdict(best['gap'], best['test_mae'] - cv_mean, best['test_mae'])

    print(
        f'   Test MAE={best["test_mae"]:.3f} | daily MAE={best["daily_mae"]:.3f} | '
        f'gap={best["gap"]:.3f} | CV={cv_mean:.3f}±{cv_std:.3f} | {verdict}'
    )

    if log_mlflow:
        import mlflow
        import mlflow.sklearn

        mlflow.set_experiment(MLFLOW_EXPERIMENT)
        with mlflow.start_run(run_name=run_name):
            flat_params = {}
            for k, v in best['params'].items():
                flat_params[f'{param_prefix}{k.replace("model__", "")}'] = v
            mlflow.log_params({
                'weather_model': 'ukmo_seamless',
                'feature_set': feature_key,
                'feature_set_label': f'UKMO | {spec["label"]}',
                'n_features': len(cols),
                'model_type': 'random_forest' if model_type == 'rf' else 'xgboost',
                'train_start': train_start,
                'train_end': train_end,
                'split_random_state': SPLIT_RANDOM_STATE,
                'cv_tolerance': CV_TOLERANCE,
                **flat_params,
            })
            mlflow.log_metrics({
                'train_mae': best['train_mae'],
                'train_r2': best['train_r2'],
                'test_mae': best['test_mae'],
                'test_r2': best['test_r2'],
                'gap': best['gap'],
                'cv_mae': cv_mean,
                'cv_std': cv_std,
                'daily_mae': best['daily_mae'],
                'daily_r2': best['daily_r2'],
            })
            mlflow.set_tag('verdict', verdict)
            mlflow.set_tag('model_type', 'random_forest' if model_type == 'rf' else 'xgboost')
            mlflow.set_tag('weather_model', 'ukmo_seamless')
            mlflow.sklearn.log_model(best['pipeline'], name='model')
        print(f'   ✓ MLflow: {run_name}')

    return {
        'run_name': run_name,
        'model_type': model_type,
        'feature_set': feature_key,
        'test_mae': best['test_mae'],
        'daily_mae': best['daily_mae'],
        'gap': best['gap'],
        'cv_mae': cv_mean,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='UKMO weather × 3 feature sets × RF/XGB → MLflow')
    parser.add_argument('--mlflow', action='store_true')
    parser.add_argument('--cases', default=','.join(CASES), help='np. cs4,panel,cs4_panel')
    parser.add_argument('--models', default='rf,xgb', help='rf,xgb')
    args = parser.parse_args()

    cases = tuple(c.strip() for c in args.cases.split(',') if c.strip())
    models = tuple(m.strip() for m in args.models.split(',') if m.strip())

    train_start, train_end = resolve_train_window(train_start=None, train_end=None)
    lat = float(os.getenv('WEATHER_LAT', '50.06'))
    lon = float(os.getenv('WEATHER_LON', '19.94'))
    print(f'Okno: {format_train_window(train_start, train_end)} | UKMO | cases={cases} models={models}')

    frame = build_ukmo_training_frame(train_start, train_end, lat, lon)
    frame['day'] = frame['day'].astype(str)

    with open(COMPARE_SPLIT_JSON, encoding='utf-8') as f:
        split = json.load(f)
    train_days = set(split['train_days'])
    test_days = set(split['test_days'])
    # tylko dni obecne w ramce UKMO
    train_mask = frame['day'].isin(train_days)
    test_mask = frame['day'].isin(test_days)
    print(
        f'✓ Split ICON (ten sam): train {train_mask.sum()} h / '
        f'test {test_mask.sum()} h '
        f'({frame.loc[train_mask, "day"].nunique()}/{frame.loc[test_mask, "day"].nunique()} dni)'
    )
    if test_mask.sum() < 50:
        raise RuntimeError('Za mało wspólnych dni testowych UKMO∩split — sprawdź cache/zakres.')

    results = []
    for model_type in models:
        for feature_key in cases:
            results.append(
                run_one(
                    model_type=model_type,
                    feature_key=feature_key,
                    frame=frame,
                    train_mask=train_mask,
                    test_mask=test_mask,
                    train_start=train_start,
                    train_end=train_end,
                    log_mlflow=args.mlflow,
                )
            )

    summary = pd.DataFrame(results).sort_values(['daily_mae', 'test_mae'])
    out = ROOT / 'data/processed/ukmo_mlflow_comparison.csv'
    summary.to_csv(out, index=False)
    print('\n' + '=' * 72)
    print('PODSUMOWANIE UKMO (sort daily_mae)')
    print('=' * 72)
    print(summary.to_string(index=False))
    print(f'\n✓ {out}')
    if args.mlflow:
        print(f'MLflow UI: http://127.0.0.1:5000  (eksperyment {MLFLOW_EXPERIMENT})')


if __name__ == '__main__':
    main()
