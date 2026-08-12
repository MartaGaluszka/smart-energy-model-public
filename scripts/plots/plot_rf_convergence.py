#!/usr/bin/env python
"""
Krzywe uczenia modelu wdrożeniowego (RF godzinowy, 16 cech).

Ten sam setup co produkcja:
  - HOURLY_FEATURE_COLUMNS_PRODUCTION (16 cech)
  - Zakres: 2025-06-01 → 2026-05-31
  - Split: 80/20 losowo po dniach, random_state=42
  - Hiperparametry RF (poza n_estimators): max_depth=6, min_samples_leaf=20, …

Wyniki:
  - reports/figures/production_learning_curves.png
  - reports/figures/rf_convergence.png  (alias — kompatybilność wsteczna)
  - data/processed/production_learning_curves.csv

Uruchomienie:
    python scripts/plot_rf_convergence.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
load_dotenv(os.path.join(ROOT, '.env'))
_db = os.getenv('DATABASE_PATH', 'data/energy_model.db')
if not os.path.isabs(_db):
    os.environ['DATABASE_PATH'] = os.path.join(ROOT, _db)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

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
    RF_RANDOM_STATE,
)

TRAIN_START = '2025-06-01'
TRAIN_END = '2026-05-31'
TREE_STEPS = [10, 20, 50, 75, 100, 150, 200, 250, 300]
OUTPUT_CSV = 'data/processed/production_learning_curves.csv'
OUTPUT_PNG = 'reports/figures/production_learning_curves.png'
OUTPUT_PNG_LEGACY = 'reports/figures/rf_convergence.png'

COLORS = {'train': '#e74c3c', 'test': '#2b6cb0', 'prod': '#276749'}


def _load_split() -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    latitude = float(os.getenv('WEATHER_LAT', '50.06'))
    longitude = float(os.getenv('WEATHER_LON', '19.94'))

    frame = load_hourly_training_frame_extended(
        latitude=latitude,
        longitude=longitude,
    )
    frame = frame[(frame['day'] >= TRAIN_START) & (frame['day'] <= TRAIN_END)]

    unique_days = frame['day'].unique()
    train_days, test_days = train_test_split(
        unique_days, test_size=0.2, random_state=42, shuffle=True,
    )

    train_mask = frame['day'].isin(train_days)
    test_mask = frame['day'].isin(test_days)

    X_train = frame.loc[train_mask, HOURLY_FEATURE_COLUMNS_PRODUCTION].replace([np.inf, -np.inf], np.nan)
    y_train = frame.loc[train_mask, TARGET_COLUMN]
    X_test = frame.loc[test_mask, HOURLY_FEATURE_COLUMNS_PRODUCTION].replace([np.inf, -np.inf], np.nan)
    y_test = frame.loc[test_mask, TARGET_COLUMN]

    print(f'✓ {len(frame)} h, {frame["day"].nunique()} dni')
    print(f'  Train: {len(y_train)} h ({len(train_days)} dni)')
    print(f'  Test:  {len(y_test)} h ({len(test_days)} dni)')
    return X_train, y_train, X_test, y_test


def _make_pipeline(n_estimators: int) -> Pipeline:
    return Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('model', RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=RF_MAX_DEPTH,
            min_samples_leaf=RF_MIN_SAMPLES_LEAF,
            min_samples_split=RF_MIN_SAMPLES_SPLIT,
            max_features=RF_MAX_FEATURES,
            random_state=RF_RANDOM_STATE,
            n_jobs=-1,
        )),
    ])


def run_convergence(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> pd.DataFrame:
    rows = []
    for n_trees in TREE_STEPS:
        model = _make_pipeline(n_trees)
        model.fit(X_train, y_train)
        train_pred = model.predict(X_train)
        test_pred = model.predict(X_test)

        train_mae = float(mean_absolute_error(y_train, train_pred))
        test_mae = float(mean_absolute_error(y_test, test_pred))
        rows.append({
            'n_estimators': n_trees,
            'train_mae': train_mae,
            'test_mae': test_mae,
            'gap': test_mae - train_mae,
            'train_r2': float(r2_score(y_train, train_pred)),
            'test_r2': float(r2_score(y_test, test_pred)),
            'is_production': n_trees == RF_N_ESTIMATORS,
        })
        print(f'  n={n_trees:>3}  train={train_mae:.3f}  test={test_mae:.3f}  gap={test_mae - train_mae:.3f}')

    return pd.DataFrame(rows)


def plot_convergence(df: pd.DataFrame, path: str) -> None:
    sns.set_theme(style='whitegrid', context='paper', font_scale=1.05)
    fig, ax = plt.subplots(figsize=(11, 6))

    ax.plot(
        df['n_estimators'], df['test_mae'],
        marker='o', linewidth=2.2, markersize=7,
        color=COLORS['test'], label='Test MAE',
    )
    ax.plot(
        df['n_estimators'], df['train_mae'],
        marker='s', linewidth=1.5, markersize=5, linestyle='--',
        color=COLORS['train'], alpha=0.75, label='Train MAE',
    )

    prod = df[df['is_production']]
    if not prod.empty:
        n_prod = int(prod['n_estimators'].iloc[0])
        test_mae_prod = float(prod['test_mae'].iloc[0])
        ax.axvline(n_prod, color=COLORS['prod'], linestyle=':', linewidth=1.8, alpha=0.85)
        ax.scatter([n_prod], [test_mae_prod], s=120, c=COLORS['prod'], zorder=5, edgecolors='white', linewidths=1.5)
        ax.annotate(
            f'Wdrożenie\nn={n_prod}, MAE={test_mae_prod:.3f}',
            xy=(n_prod, test_mae_prod),
            xytext=(12, 18),
            textcoords='offset points',
            fontsize=9,
            color=COLORS['prod'],
            fontweight='semibold',
            bbox=dict(boxstyle='round,pad=0.35', facecolor='white', edgecolor=COLORS['prod'], alpha=0.9),
        )

    ax.set_xlabel('Liczba drzew (n_estimators)', fontsize=11)
    ax.set_ylabel('MAE [kWh/h]')
    ax.set_title(
        'Krzywe uczenia — model wdrożeniowy RF (16 cech, split 80/20 po dniach)',
        fontsize=13, fontweight='bold', pad=12,
    )
    ax.legend(loc='upper right', framealpha=0.95)
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.set_axisbelow(True)

    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def main() -> None:
    os.makedirs('docs', exist_ok=True)
    os.makedirs('data/processed', exist_ok=True)

    print('=' * 72)
    print('KRZYWE UCZENIA — MODEL WDROŻENIOWY (RF, 16 cech)')
    print('=' * 72)
    print(f'Zakres: {TRAIN_START} → {TRAIN_END}')
    print(f'Hiperparametry: max_depth={RF_MAX_DEPTH}, min_samples_leaf={RF_MIN_SAMPLES_LEAF}, '
          f'max_features={RF_MAX_FEATURES}')
    print(f'Produkcja: n_estimators={RF_N_ESTIMATORS}')

    print('\n[1] Ładowanie i podział danych...')
    X_train, y_train, X_test, y_test = _load_split()

    print('\n[2] Trening dla kolejnych n_estimators...')
    df = run_convergence(X_train, y_train, X_test, y_test)
    df.to_csv(OUTPUT_CSV, index=False)

    print('\n[3] Wykres...')
    plot_convergence(df, OUTPUT_PNG)
    plot_convergence(df, OUTPUT_PNG_LEGACY)

    print(f'\n✓ {OUTPUT_CSV}')
    print(f'✓ {OUTPUT_PNG}')
    print(f'✓ {OUTPUT_PNG_LEGACY}')
    print('\n' + '=' * 72)
    print('GOTOWE')
    print('=' * 72)


if __name__ == '__main__':
    main()
