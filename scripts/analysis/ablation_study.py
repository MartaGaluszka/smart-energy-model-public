#!/usr/bin/env python
"""Studium ablacji cech PV — podział 80/20 po dniach, rok 2025-06 → 2026-05."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, '.env'))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

from src.features.pv_features_hourly_extended import (
    TARGET_COLUMN,
    load_hourly_training_frame_extended,
)


def _db_path() -> str:
    """Ścieżka do SQLite — zawsze względem katalogu projektu (nie cwd notebooka)."""
    raw = os.getenv('DATABASE_PATH', 'data/energy_model.db')
    if os.path.isabs(raw):
        return raw
    return os.path.join(ROOT, raw)

TRAIN_START = '2025-06-01'
TRAIN_END = '2026-05-31'
RANDOM_STATE = 42
N_ESTIMATORS = 200
MAX_DEPTH = 8

_WEATHER = [
    'hour', 'temp_c', 'humidity_pct', 'cloud_cover_pct',
    'radiation_wm2', 'wind_speed_ms',
]
_CALENDAR = ['doy_sin', 'doy_cos', 'month']
_SUN = [
    'sunrise_hour', 'sunset_hour', 'day_length_hours',
    'hours_since_sunrise', 'hours_until_sunset', 'sun_position', 'is_daylight',
]
_RULES = ['snow_on_panels', 'snow_on_panels_prev', 'likely_fog_day']

# Zestawy cech (kolejność ablacji)
FEATURE_GROUPS = {
    '1_Baza': ['hour'],
    '2_Pogoda': _WEATHER.copy(),
    '3_Kalendarz': _WEATHER + _CALENDAR,
    '3_Pogoda_Slonce': _WEATHER + _SUN,
    '3_Pogoda_Slonce_Reguly': _WEATHER + _SUN + _RULES,  # rekomendowany produkcyjny
    '4_Reguly': _WEATHER + _CALENDAR + _SUN + _RULES,    # legacy (z kalendarzem)
}

# Raport decyzyjny: kalendarz vs słońce vs rekomendowany zestaw
CALENDAR_COMPARISON_PHASES = [
    '2_Pogoda',
    '3_Kalendarz',
    '3_Pogoda_Slonce',
    '3_Pogoda_Slonce_Reguly',
    '4_Reguly',
]

TREE_STEPS = [10, 20, 50, 100, 150, 200]


def _load_and_split() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = load_hourly_training_frame_extended(
        db_path=_db_path(),
        start_date=TRAIN_START,
        end_date=TRAIN_END,
    )
    unique_days = df['day'].unique()
    train_days, test_days = train_test_split(
        unique_days, test_size=0.2, random_state=RANDOM_STATE,
    )
    train_df = df[df['day'].isin(train_days)]
    test_df = df[df['day'].isin(test_days)]
    print(f'Zbiór: {TRAIN_START} → {TRAIN_END}')
    print(f'Train: {len(train_df)} h ({len(train_days)} dni) | Test: {len(test_df)} h ({len(test_days)} dni)')
    return train_df, test_df


def _evaluate_phase(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    phase_key: str,
    features: list[str],
) -> dict:
    model = RandomForestRegressor(
        n_estimators=N_ESTIMATORS,
        max_depth=MAX_DEPTH,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    y_train = train_df[TARGET_COLUMN]
    y_test = test_df[TARGET_COLUMN]
    model.fit(train_df[features], y_train)
    pred = model.predict(test_df[features])

    mae = float(mean_absolute_error(y_test, pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
    r2 = float(r2_score(y_test, pred))

    return {
        'Etap': phase_key,
        'N_cech': len(features),
        'Test_MAE': mae,
        'Test_RMSE': rmse,
        'Test_R2': r2,
    }


def run_ablation() -> pd.DataFrame:
    train_df, test_df = _load_and_split()
    results = []
    for name, features in FEATURE_GROUPS.items():
        row = _evaluate_phase(train_df, test_df, name, features)
        results.append(row)
        print(f'  {name}: MAE={row["Test_MAE"]:.3f}  R²={row["Test_R2"]:.3f}')

    out = pd.DataFrame(results)
    path = os.path.join(ROOT, 'data', 'processed', 'ablation_results.csv')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.to_csv(path, index=False)
    print(f'✓ {path}')
    return out


def run_calendar_comparison() -> pd.DataFrame:
    """Porównanie: pogoda vs kalendarz vs pogoda+słońce vs pełny model."""
    train_df, test_df = _load_and_split()
    rows = []
    for phase_key in CALENDAR_COMPARISON_PHASES:
        features = FEATURE_GROUPS[phase_key]
        row = _evaluate_phase(train_df, test_df, phase_key, features)
        rows.append(row)
        print(
            f'  {phase_key:18s}  cech={row["N_cech"]:2d}  '
            f'MAE={row["Test_MAE"]:.3f}  RMSE={row["Test_RMSE"]:.3f}  R²={row["Test_R2"]:.3f}'
        )

    df = pd.DataFrame(rows)
    baseline_mae = df.loc[df['Etap'] == '2_Pogoda', 'Test_MAE'].iloc[0]
    df['Delta_MAE_vs_Pogoda'] = df['Test_MAE'] - baseline_mae

    full_mae = df.loc[df['Etap'] == '4_Reguly', 'Test_MAE'].iloc[0]
    rec_mae = df.loc[df['Etap'] == '3_Pogoda_Slonce_Reguly', 'Test_MAE'].iloc[0]
    sun_mae = df.loc[df['Etap'] == '3_Pogoda_Slonce', 'Test_MAE'].iloc[0]
    df['Delta_MAE_vs_Pelny'] = df['Test_MAE'] - full_mae
    df['Wdrozony'] = df['Etap'] == '3_Pogoda_Slonce_Reguly'
    df['Rekomendowany'] = df['Wdrozony']  # alias wsteczny

    path = os.path.join(ROOT, 'data', 'processed', 'calendar_ablation_comparison.csv')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False)
    print(f'✓ {path}')
    print(f'\n  ★ Wdrożone (16 cech) vs Legacy (19 cech):  ΔMAE = {rec_mae - full_mae:+.3f} kWh/h')
    print(f'  Pogoda+Słońce vs Legacy (19):              ΔMAE = {sun_mae - full_mae:+.3f} kWh/h')
    cal_mae = df.loc[df['Etap'] == '3_Kalendarz', 'Test_MAE'].iloc[0]
    print(f'  Kalendarz vs Pogoda:                       ΔMAE = {cal_mae - baseline_mae:+.3f} kWh/h')
    rules_delta = rec_mae - sun_mae
    print(f'  Reguły (śnieg/mgła) na słońcu:              ΔMAE = {rules_delta:+.3f} kWh/h')
    return df


def run_learning_curves() -> pd.DataFrame:
    train_df, test_df = _load_and_split()
    all_results = []
    for name, features in FEATURE_GROUPS.items():
        for n_trees in TREE_STEPS:
            model = RandomForestRegressor(
                n_estimators=n_trees, max_depth=MAX_DEPTH, n_jobs=-1, random_state=RANDOM_STATE,
            )
            model.fit(train_df[features], train_df[TARGET_COLUMN])
            test_mae = float(mean_absolute_error(
                test_df[TARGET_COLUMN],
                model.predict(test_df[features]),
            ))
            all_results.append({'Etap': name, 'Drzewa': n_trees, 'Test_MAE': test_mae})

    out = pd.DataFrame(all_results)
    path = os.path.join(ROOT, 'data', 'processed', 'learning_curves.csv')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.to_csv(path, index=False)
    print(f'✓ {path}')
    return out


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Ablacja cech PV')
    parser.add_argument('--calendar-only', action='store_true', help='Tylko porównanie kalendarz vs słońce')
    args = parser.parse_args()

    print('=' * 60)
    if args.calendar_only:
        print('RAPORT: Kalendarz (month/doy) vs Pogoda+Słońce')
        print('=' * 60)
        run_calendar_comparison()
    else:
        print('ABLACJA CECH PV')
        print('=' * 60)
        run_ablation()
        print()
        print('=' * 60)
        print('RAPORT: Kalendarz vs Pogoda+Słońce')
        print('=' * 60)
        run_calendar_comparison()
        print()
        run_learning_curves()
