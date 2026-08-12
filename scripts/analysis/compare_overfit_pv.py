"""
Porównanie legacy (7d/3°C) vs model topnienia + diagnostyka przeuczenia.

Metryki:
  - MAE train / test (holdout czasowy od ML_TEST_START)
  - MAE CV (GroupKFold po miesiącach, n=5)
  - gap = test − train  (duży gap → ryzyko przeuczenia)
  - cv_vs_test = test − cv_mean (duży → test trudniejszy niż średni fold)

Uruchomienie:
    python scripts/compare_overfit_pv.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.pipeline import Pipeline

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

from src.features.pv_features import (
    DEFAULT_SNOW_THAW_TEMP_C,
    DEFAULT_SNOW_WINDOW_DAYS,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    apply_snow_panel_flags,
    load_training_frame,
    time_train_test_split,
)
from src.features.snow_melt_model import (
    apply_melt_snow_flags,
    calibrate_snow_melt_params,
)

load_dotenv()

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')
LOCATION = os.getenv('WEATHER_LOCATION')
OUT_CSV = os.getenv('OVERFIT_COMPARE_CSV', 'data/processed/overfit_compare.csv')


def _rf_pipeline() -> Pipeline:
    return Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('model', RandomForestRegressor(
            n_estimators=300, max_depth=12, min_samples_leaf=2,
            random_state=42, n_jobs=-1,
        )),
    ])


def _groups(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(frame['day']).dt.to_period('M').astype(str)


def _cv_mae(frame: pd.DataFrame, y: pd.Series, groups: pd.Series, n_splits: int = 5) -> tuple[float, float]:
    cv = GroupKFold(n_splits=n_splits)
    model = _rf_pipeline()
    scores = cross_val_score(
        model, frame[FEATURE_COLUMNS], y, groups=groups,
        cv=cv, scoring='neg_mean_absolute_error',
    )
    mae = -scores
    return float(mae.mean()), float(mae.std())


def _train_test_mae(
    frame: pd.DataFrame,
    test_start: str,
) -> tuple[float, float, int, int]:
    split = time_train_test_split(frame, test_start=test_start)
    model = _rf_pipeline()
    model.fit(split.X_train, split.y_train)
    train_mae = float(mean_absolute_error(split.y_train, model.predict(split.X_train)))
    test_mae = float(mean_absolute_error(split.y_test, model.predict(split.X_test)))
    return train_mae, test_mae, len(split.y_train), len(split.y_test)


def _frame_legacy() -> pd.DataFrame:
    return load_training_frame(snow_mode='legacy')


def _frame_melt_no_leak(test_start: str) -> pd.DataFrame:
    """Kalibracja melt tylko na train, flagi na całej ramce."""
    base = load_training_frame(snow_mode='none')
    train = base[base['day'] < test_start]
    params, _ = calibrate_snow_melt_params(train)
    start, end = str(base['day'].min()), str(base['day'].max())
    return apply_melt_snow_flags(base, DB_PATH, start, end, LOCATION, params=params), params


def _overfit_label(gap: float, train_mae: float) -> str:
    ratio = gap / max(train_mae, 0.1)
    if gap < 0.4 and ratio < 0.25:
        return 'niskie ryzyko'
    if gap < 0.9 and ratio < 0.45:
        return 'umiarkowane'
    return 'podwyższone'


def main() -> None:
    test_start = os.getenv('ML_TEST_START', '2026-02-01')
    n_splits = 5

    print('=' * 72)
    print('Legacy (7d/3°C) vs model topnienia — przeuczenie')
    print(f'Holdout test od: {test_start} | CV: GroupKFold n={n_splits} (miesiące)')
    print('=' * 72)

    rows: list[dict] = []

    for label, frame in [
        ('legacy_7d_3c', _frame_legacy()),
    ]:
        y = frame[TARGET_COLUMN]
        groups = _groups(frame)
        cv_mean, cv_std = _cv_mae(frame, y, groups, n_splits)
        train_mae, test_mae, n_train, n_test = _train_test_mae(frame, test_start)
        gap = test_mae - train_mae
        rows.append({
            'snow_model': label,
            'n_train': n_train,
            'n_test': n_test,
            'mae_train': round(train_mae, 3),
            'mae_test': round(test_mae, 3),
            'mae_cv_mean': round(cv_mean, 3),
            'mae_cv_std': round(cv_std, 3),
            'gap_test_minus_train': round(gap, 3),
            'test_minus_cv': round(test_mae - cv_mean, 3),
            'overfit_risk': _overfit_label(gap, train_mae),
        })

    melt_frame, melt_params = _frame_melt_no_leak(test_start)
    y_m = melt_frame[TARGET_COLUMN]
    groups_m = _groups(melt_frame)
    cv_mean_m, cv_std_m = _cv_mae(melt_frame, y_m, groups_m, n_splits)
    train_mae_m, test_mae_m, n_train_m, n_test_m = _train_test_mae(melt_frame, test_start)
    gap_m = test_mae_m - train_mae_m
    rows.append({
        'snow_model': 'melt_formula',
        'n_train': n_train_m,
        'n_test': n_test_m,
        'mae_train': round(train_mae_m, 3),
        'mae_test': round(test_mae_m, 3),
        'mae_cv_mean': round(cv_mean_m, 3),
        'mae_cv_std': round(cv_std_m, 3),
        'gap_test_minus_train': round(gap_m, 3),
        'test_minus_cv': round(test_mae_m - cv_mean_m, 3),
        'overfit_risk': _overfit_label(gap_m, train_mae_m),
        'melt_t_c': melt_params.t_melt_c,
        'melt_k': melt_params.k_melt_cm_per_h,
        'melt_slide': melt_params.slide_fraction,
    })

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(OUT_CSV) or '.', exist_ok=True)
    df.to_csv(OUT_CSV, index=False)

    print('\n', df.to_string(index=False))
    print(f'\n💾 Zapisano: {OUT_CSV}')

    print('\n' + '-' * 72)
    print('Jak czytać:')
    print('  gap_test_minus_train  — duży (>1 kWh) → model lepiej na train niż test')
    print('  test_minus_cv         — test vs średni fold CV (sezonowość / trudny test)')
    print('  mae_cv_std            — stabilność między miesiącami (zima vs lato)')
    print('-' * 72)

    leg = df[df['snow_model'] == 'legacy_7d_3c'].iloc[0]
    mel = df[df['snow_model'] == 'melt_formula'].iloc[0]
    print('\n📌 Wnioski skrótowe:')
    print(f'   Legacy:  train={leg["mae_train"]} test={leg["mae_test"]} CV={leg["mae_cv_mean"]} → {leg["overfit_risk"]}')
    print(f'   Melt:    train={mel["mae_train"]} test={mel["mae_test"]} CV={mel["mae_cv_mean"]} → {mel["overfit_risk"]}')
    better = 'melt' if mel['mae_test'] < leg['mae_test'] else 'legacy'
    print(f'   Lepszy test MAE: {better} (różnica {abs(mel["mae_test"] - leg["mae_test"]):.3f} kWh)')


if __name__ == '__main__':
    main()
