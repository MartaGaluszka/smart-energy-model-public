#!/usr/bin/env python
"""
Porównanie algorytmów na modelu godzinowym — ten sam split co produkcja.

Modele: Ridge (regresja liniowa), Random Forest (parametry produkcyjne), XGBoost.

Dane:
  - Zakres: 2025-06-01 → 2026-05-31
  - Cechy: HOURLY_FEATURE_COLUMNS_PRODUCTION (16)
  - Split: 80/20 losowo po dniach, random_state=42

Wyniki:
  - data/processed/hourly_algorithm_comparison.csv
  - data/processed/hourly_algorithm_predictions.csv
  - reports/figures/hourly_algorithm_comparison.png
  - reports/figures/hourly_algorithm_errors_mae_rmse.png
  - reports/figures/hourly_algorithm_r2.png
  - reports/figures/hourly_algorithm_scatter.png
  - reports/figures/hourly_algorithm_learning_curves.png

Uruchomienie:
    python scripts/compare_algorithms_hourly.py
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
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    from xgboost import XGBRegressor
except ImportError:  # pragma: no cover
    XGBRegressor = None

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
    _metrics,
)

TRAIN_START = '2025-06-01'
TRAIN_END = '2026-05-31'
RESULTS_CSV = 'data/processed/hourly_algorithm_comparison.csv'
PREDICTIONS_CSV = 'data/processed/hourly_algorithm_predictions.csv'
CHART_OVERVIEW = 'reports/figures/hourly_algorithm_comparison.png'
CHART_ERRORS = 'reports/figures/hourly_algorithm_errors_mae_rmse.png'
CHART_R2 = 'reports/figures/hourly_algorithm_r2.png'
CHART_SCATTER = 'reports/figures/hourly_algorithm_scatter.png'
CHART_LEARNING = 'reports/figures/hourly_algorithm_learning_curves.png'
LEARNING_CSV = 'data/processed/hourly_algorithm_learning_curves.csv'

# Kroki złożoności — RF/XGB: n_estimators; Ridge: malejące α (większa złożoność →)
TREE_STEPS = [10, 20, 50, 75, 100, 150, 200]
RIDGE_ALPHAS = [5000, 2000, 1000, 500, 200, 100, 50]

MODEL_LABELS = {
    'ridge_linear': 'Ridge',
    'random_forest_production': 'RF (prod.)',
    'xgboost': 'XGBoost',
}

MODEL_ORDER = ['ridge_linear', 'random_forest_production', 'xgboost']

COLORS = {
    'train': '#3498db',
    'test': '#e74c3c',
    'mae': '#2b6cb0',
    'rmse': '#c05621',
    'r2_train': '#805ad5',
    'r2_test': '#38a169',
    'ridge': '#9b59b6',
    'rf': '#27ae60',
    'xgb': '#f39c12',
    'diagonal': '#c53030',
}


def _gap_verdict(gap: float) -> str:
    if gap < 0.15:
        return '✅ Nie przeuczony'
    if gap < 0.35:
        return '⚠️  Lekkie przeuczenie'
    return '❌ Przeuczony'


def _daily_metrics(meta_test: pd.DataFrame, y_true: pd.Series, y_pred: np.ndarray) -> dict:
    frame = meta_test.copy()
    frame['y_true'] = y_true.values
    frame['y_pred'] = y_pred
    daily_true = frame.groupby('day')['y_true'].sum()
    daily_pred = frame.groupby('day')['y_pred'].sum()
    return {
        'daily_mae': float(mean_absolute_error(daily_true, daily_pred)),
        'daily_r2': float(r2_score(daily_true, daily_pred)),
    }


def _evaluate_model(
    name: str,
    model,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    meta_test: pd.DataFrame,
) -> tuple[dict, pd.DataFrame]:
    model.fit(X_train, y_train)
    train_pred = model.predict(X_train)
    test_pred = model.predict(X_test)

    train_m = _metrics(y_train, train_pred)
    test_m = _metrics(y_test, test_pred)
    gap = test_m['mae'] - train_m['mae']
    daily = _daily_metrics(meta_test, y_test, test_pred)

    pred_df = meta_test.copy()
    pred_df['model'] = name
    pred_df['y_true'] = y_test.values
    pred_df['y_pred'] = test_pred
    pred_df['residual'] = pred_df['y_true'] - pred_df['y_pred']
    pred_df['abs_error'] = pred_df['residual'].abs()

    row = {
        'model': name,
        'label': MODEL_LABELS.get(name, name),
        'n_features': X_train.shape[1],
        'train_mae_hour': train_m['mae'],
        'train_rmse_hour': train_m['rmse'],
        'train_r2_hour': train_m['r2'],
        'test_mae_hour': test_m['mae'],
        'test_rmse_hour': test_m['rmse'],
        'test_r2_hour': test_m['r2'],
        'gap_hour': gap,
        'gap_pct_of_test': gap / test_m['mae'] * 100 if test_m['mae'] else float('nan'),
        'daily_mae': daily['daily_mae'],
        'daily_r2': daily['daily_r2'],
        'verdict': _gap_verdict(gap),
    }
    return row, pred_df


def _make_ridge_pipeline(alpha: float = 100.0) -> Pipeline:
    return Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler()),
        ('model', Ridge(alpha=alpha, random_state=42)),
    ])


def _make_rf_pipeline(n_estimators: int = RF_N_ESTIMATORS) -> Pipeline:
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


def _make_xgb_pipeline(n_estimators: int = 200) -> Pipeline | None:
    if XGBRegressor is None:
        return None
    return Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('model', XGBRegressor(
            n_estimators=n_estimators,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=42,
            objective='reg:squarederror',
            n_jobs=-1,
        )),
    ])


def _get_models() -> dict[str, Pipeline]:
    models: dict[str, Pipeline] = {
        'ridge_linear': _make_ridge_pipeline(100.0),
        'random_forest_production': _make_rf_pipeline(RF_N_ESTIMATORS),
    }
    xgb = _make_xgb_pipeline(200)
    if xgb is not None:
        models['xgboost'] = xgb
    return models


def _fit_mae(
    model: Pipeline,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> tuple[float, float]:
    model.fit(X_train, y_train)
    train_mae = float(mean_absolute_error(y_train, model.predict(X_train)))
    test_mae = float(mean_absolute_error(y_test, model.predict(X_test)))
    return train_mae, test_mae


def run_learning_curves(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> pd.DataFrame:
    """Krzywe złożoności: MAE vs n_estimators (RF/XGB) lub α (Ridge)."""
    rows: list[dict] = []

    for n_trees in TREE_STEPS:
        train_mae, test_mae = _fit_mae(
            _make_rf_pipeline(n_trees), X_train, y_train, X_test, y_test,
        )
        rows.append({
            'model': 'random_forest_production',
            'label': MODEL_LABELS['random_forest_production'],
            'complexity_axis': 'n_estimators',
            'complexity_value': n_trees,
            'x_axis': n_trees,
            'train_mae': train_mae,
            'test_mae': test_mae,
        })

    if XGBRegressor is not None:
        for n_trees in TREE_STEPS:
            train_mae, test_mae = _fit_mae(
                _make_xgb_pipeline(n_trees), X_train, y_train, X_test, y_test,
            )
            rows.append({
                'model': 'xgboost',
                'label': MODEL_LABELS['xgboost'],
                'complexity_axis': 'n_estimators',
                'complexity_value': n_trees,
                'x_axis': n_trees,
                'train_mae': train_mae,
                'test_mae': test_mae,
            })

    for x_pos, alpha in zip(TREE_STEPS, RIDGE_ALPHAS):
        train_mae, test_mae = _fit_mae(
            _make_ridge_pipeline(alpha), X_train, y_train, X_test, y_test,
        )
        rows.append({
            'model': 'ridge_linear',
            'label': MODEL_LABELS['ridge_linear'],
            'complexity_axis': 'alpha',
            'complexity_value': alpha,
            'x_axis': x_pos,
            'train_mae': train_mae,
            'test_mae': test_mae,
        })

    return pd.DataFrame(rows)


def _plot_learning_curves(lc_df: pd.DataFrame, path: str) -> None:
    """Wszystkie modele na jednym wykresie — test (solid) i train (przerywane)."""
    sns.set_theme(style='whitegrid', context='paper', font_scale=1.05)
    fig, ax = plt.subplots(figsize=(11, 6))

    line_colors = {
        'ridge_linear': COLORS['ridge'],
        'random_forest_production': COLORS['rf'],
        'xgboost': COLORS['xgb'],
    }

    for model_key in MODEL_ORDER:
        if model_key not in lc_df['model'].values:
            continue
        sub = lc_df[lc_df['model'] == model_key].sort_values('x_axis')
        color = line_colors[model_key]
        label = MODEL_LABELS[model_key]

        ax.plot(
            sub['x_axis'], sub['test_mae'],
            marker='o', linewidth=2.2, markersize=7,
            color=color, label=f'{label} — test',
        )
        ax.plot(
            sub['x_axis'], sub['train_mae'],
            marker='s', linewidth=1.5, markersize=5, linestyle='--',
            color=color, alpha=0.55, label=f'{label} — train',
        )

    ax.set_xlabel(
        'Złożoność modelu: n_estimators (RF, XGBoost)  ·  Ridge: α = 5000 → 50',
        fontsize=11,
    )
    ax.set_ylabel('MAE [kWh/h]')
    ax.set_title(
        'Krzywe uczenia — MAE vs złożoność (model godzinowy, 16 cech, split 80/20)',
        fontsize=13, fontweight='bold', pad=12,
    )
    ax.legend(loc='upper right', fontsize=9, ncol=2, framealpha=0.95)
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.set_axisbelow(True)

    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def _ordered_results(results: pd.DataFrame) -> pd.DataFrame:
    order = {m: i for i, m in enumerate(MODEL_ORDER)}
    out = results.copy()
    out['_sort'] = out['model'].map(order)
    return out.sort_values('_sort').drop(columns='_sort')


def _plot_overview(results: pd.DataFrame, path: str) -> None:
    plot_df = _ordered_results(results)
    x = np.arange(len(plot_df))
    width = 0.35

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    ax = axes[0]
    ax.bar(x - width / 2, plot_df['train_mae_hour'], width, label='Train MAE', color=COLORS['train'])
    ax.bar(x + width / 2, plot_df['test_mae_hour'], width, label='Test MAE', color=COLORS['test'])
    ax.set_xticks(x)
    ax.set_xticklabels(plot_df['label'])
    ax.set_ylabel('MAE [kWh/h]')
    ax.set_title('Model godzinowy — błąd train vs test (80/20 po dniach)')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    ax = axes[1]
    model_colors = [COLORS['ridge'], COLORS['rf'], COLORS['xgb']][: len(plot_df)]
    ax.bar(plot_df['label'], plot_df['gap_hour'], color=model_colors)
    ax.set_ylabel('Gap (test − train) [kWh/h]')
    ax.set_title('Przeuczenie — gap train/test')
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()


def _plot_errors_mae_rmse(results: pd.DataFrame, path: str) -> None:
    """MAE i RMSE — train vs test dla każdego algorytmu."""
    sns.set_theme(style='whitegrid', context='paper', font_scale=1.05)
    plot_df = _ordered_results(results)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    x = np.arange(len(plot_df))
    width = 0.2
    offsets = [-1.5, -0.5, 0.5, 1.5]

    for ax, split, mae_col, rmse_col, title in [
        (axes[0], 'Train', 'train_mae_hour', 'train_rmse_hour', 'Zbiór treningowy'),
        (axes[1], 'Test', 'test_mae_hour', 'test_rmse_hour', 'Zbiór testowy'),
    ]:
        bars_mae = ax.bar(
            x + offsets[0] * width, plot_df[mae_col], width,
            label='MAE', color=COLORS['mae'], alpha=0.9, edgecolor='white',
        )
        bars_rmse = ax.bar(
            x + offsets[2] * width, plot_df[rmse_col], width,
            label='RMSE', color=COLORS['rmse'], alpha=0.9, edgecolor='white',
        )
        for bar in list(bars_mae) + list(bars_rmse):
            h = bar.get_height()
            ax.annotate(
                f'{h:.2f}',
                xy=(bar.get_x() + bar.get_width() / 2, h),
                xytext=(0, 4),
                textcoords='offset points',
                ha='center', va='bottom', fontsize=8,
            )
        ax.set_xticks(x)
        ax.set_xticklabels(plot_df['label'])
        ax.set_ylabel('Błąd [kWh/h]')
        ax.set_title(f'{title} — MAE / RMSE')
        ax.legend(loc='upper right')
        ax.grid(True, axis='y', linestyle='--', alpha=0.5)
        ax.set_axisbelow(True)

    fig.suptitle(
        'Porównanie algorytmów (model godzinowy, 16 cech, split 80/20 po dniach)',
        fontsize=13, fontweight='bold',
    )
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def _plot_r2(results: pd.DataFrame, path: str) -> None:
    """R² train vs test."""
    sns.set_theme(style='whitegrid', context='paper', font_scale=1.05)
    plot_df = _ordered_results(results)

    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(plot_df))
    width = 0.35

    bars_tr = ax.bar(
        x - width / 2, plot_df['train_r2_hour'], width,
        label='Train R²', color=COLORS['r2_train'], alpha=0.9, edgecolor='white',
    )
    bars_te = ax.bar(
        x + width / 2, plot_df['test_r2_hour'], width,
        label='Test R²', color=COLORS['r2_test'], alpha=0.9, edgecolor='white',
    )

    for bar in list(bars_tr) + list(bars_te):
        h = bar.get_height()
        ax.annotate(
            f'{h:.3f}',
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 4),
            textcoords='offset points',
            ha='center', va='bottom', fontsize=9, fontweight='medium',
        )

    ax.set_xticks(x)
    ax.set_xticklabels(plot_df['label'])
    ax.set_ylabel('$R^2$')
    ax.set_ylim(0, 1.05)
    ax.set_title(
        'Porównanie algorytmów — $R^2$ (train vs test, model godzinowy)',
        fontsize=13, fontweight='bold', pad=12,
    )
    ax.legend(loc='lower right', framealpha=0.95)
    ax.grid(True, axis='y', linestyle='--', alpha=0.5)
    ax.set_axisbelow(True)

    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def _plot_scatter(predictions: pd.DataFrame, results: pd.DataFrame, path: str) -> None:
    """Rzeczywistość vs prognoza na zbiorze testowym — panel 1×3."""
    sns.set_theme(style='whitegrid', context='paper', font_scale=1.05)
    models_present = [m for m in MODEL_ORDER if m in predictions['model'].unique()]
    n = len(models_present)
    fig, axes = plt.subplots(1, n, figsize=(5 * n, 5), constrained_layout=True)
    if n == 1:
        axes = [axes]

    scatter_colors = {
        'ridge_linear': COLORS['ridge'],
        'random_forest_production': COLORS['rf'],
        'xgboost': COLORS['xgb'],
    }

    all_y = predictions['y_true'].values
    all_pred = predictions['y_pred'].values
    lim_hi = max(all_y.max(), all_pred.max()) * 1.05

    for ax, model_key in zip(axes, models_present):
        sub = predictions[predictions['model'] == model_key]
        r2 = results.loc[results['model'] == model_key, 'test_r2_hour'].iloc[0]
        mae = results.loc[results['model'] == model_key, 'test_mae_hour'].iloc[0]
        label = MODEL_LABELS.get(model_key, model_key)
        color = scatter_colors.get(model_key, COLORS['mae'])

        ax.scatter(
            sub['y_true'], sub['y_pred'],
            alpha=0.45, s=20, c=color, edgecolors='none',
        )
        ax.plot([0, lim_hi], [0, lim_hi], color=COLORS['diagonal'], linewidth=1.8, linestyle='--')
        ax.set_xlim(0, lim_hi)
        ax.set_ylim(0, lim_hi)
        ax.set_aspect('equal', adjustable='box')
        ax.set_title(f'{label}\n$R^2$ = {r2:.3f}  ·  MAE = {mae:.3f} kWh/h', fontweight='semibold')
        ax.set_xlabel('Rzeczywista PV [kWh/h]')
        ax.set_ylabel('Prognozowana PV [kWh/h]')

    fig.suptitle(
        'Test set: rzeczywistość vs prognoza (80/20 po dniach, 2025-06 → 2026-05)',
        fontsize=13, fontweight='bold',
    )
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def main() -> None:
    os.makedirs('docs', exist_ok=True)
    os.makedirs('data/processed', exist_ok=True)

    latitude = float(os.getenv('WEATHER_LAT', '50.06'))
    longitude = float(os.getenv('WEATHER_LON', '19.94'))

    print('=' * 72)
    print('PORÓWNANIE ALGORYTMÓW — MODEL GODZINOWY (split 80/20 po dniach)')
    print('=' * 72)
    print(f'Zakres: {TRAIN_START} → {TRAIN_END}')
    print(f'Cechy: {len(HOURLY_FEATURE_COLUMNS_PRODUCTION)}')

    print('\n[1] Ładowanie danych...')
    frame = load_hourly_training_frame_extended(
        latitude=latitude,
        longitude=longitude,
    )
    frame = frame[(frame['day'] >= TRAIN_START) & (frame['day'] <= TRAIN_END)]
    print(f'✓ {len(frame)} rekordów, {frame["day"].nunique()} dni')

    unique_days = frame['day'].unique()
    train_days, test_days = train_test_split(
        unique_days,
        test_size=0.2,
        random_state=42,
        shuffle=True,
    )

    train_mask = frame['day'].isin(train_days)
    test_mask = frame['day'].isin(test_days)

    X_train = frame.loc[train_mask, HOURLY_FEATURE_COLUMNS_PRODUCTION].replace([np.inf, -np.inf], np.nan)
    y_train = frame.loc[train_mask, TARGET_COLUMN]
    X_test = frame.loc[test_mask, HOURLY_FEATURE_COLUMNS_PRODUCTION].replace([np.inf, -np.inf], np.nan)
    y_test = frame.loc[test_mask, TARGET_COLUMN]
    meta_test = frame.loc[test_mask, ['day', 'hour']]

    print(f'Train: {len(y_train)} h ({len(train_days)} dni)')
    print(f'Test:  {len(y_test)} h ({len(test_days)} dni)')

    models = _get_models()
    if XGBRegressor is None:
        print('\n⚠️  xgboost nie zainstalowany — pomijam XGBoost')

    print('\n[2] Trening i ocena...')
    rows = []
    pred_frames = []
    for name, model in models.items():
        print(f'  → {name}...')
        row, pred_df = _evaluate_model(name, model, X_train, y_train, X_test, y_test, meta_test)
        rows.append(row)
        pred_frames.append(pred_df)

    results = pd.DataFrame(rows)
    results = _ordered_results(results)
    all_preds = pd.concat(pred_frames, ignore_index=True)

    results.to_csv(RESULTS_CSV, index=False)
    all_preds.to_csv(PREDICTIONS_CSV, index=False)

    print('\n[3] Krzywe uczenia (złożoność vs MAE)...')
    lc_df = run_learning_curves(X_train, y_train, X_test, y_test)
    lc_df.to_csv(LEARNING_CSV, index=False)
    _plot_learning_curves(lc_df, CHART_LEARNING)

    print('\n[4] Wykresy...')
    _plot_overview(results, CHART_OVERVIEW)
    _plot_errors_mae_rmse(results, CHART_ERRORS)
    _plot_r2(results, CHART_R2)
    _plot_scatter(all_preds, results, CHART_SCATTER)

    print('\n[5] Wyniki (Test MAE):')
    display_cols = [
        'label', 'train_mae_hour', 'test_mae_hour', 'train_rmse_hour', 'test_rmse_hour',
        'train_r2_hour', 'test_r2_hour', 'gap_hour', 'daily_mae', 'verdict',
    ]
    print(results[display_cols].to_string(index=False, float_format=lambda x: f'{x:.3f}'))

    print(f'\n✓ {RESULTS_CSV}')
    print(f'✓ {PREDICTIONS_CSV}')
    print(f'✓ {CHART_OVERVIEW}')
    print(f'✓ {CHART_ERRORS}')
    print(f'✓ {CHART_R2}')
    print(f'✓ {CHART_SCATTER}')
    print(f'✓ {LEARNING_CSV}')
    print(f'✓ {CHART_LEARNING}')
    print('\n' + '=' * 72)
    print('GOTOWE')
    print('=' * 72)


if __name__ == '__main__':
    main()
