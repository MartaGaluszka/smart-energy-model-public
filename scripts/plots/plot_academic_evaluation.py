#!/usr/bin/env python
"""
Akademickie wykresy ewaluacyjne RF — 4 fazy inżynierii cech (model produkcyjny).

Wykres 1: Rzeczywistość vs Prognoza (scatter + y=x, R²) — odpowiednik Accuracy
Wykres 2: Spadek MAE i RMSE między fazami — odpowiednik F1 / Lost Accuracy

Fazy (kumulatywnie, bez kalendarza — zgodnie z wdrożeniem 2026-07-13):
  1. Baza → 2. Pogoda → 3. Pogoda+Słońce → 4. Produkcja (16 cech)

Uruchomienie:
    python scripts/plot_academic_evaluation.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from scripts.ablation_study import (
    FEATURE_GROUPS,
    MAX_DEPTH,
    N_ESTIMATORS,
    RANDOM_STATE,
    TARGET_COLUMN,
    _load_and_split,
)

# 4 fazy na wykresach akademickich (ścieżka produkcyjna, bez 3_Kalendarz / legacy 4_Reguly)
ACADEMIC_PHASES = [
    '1_Baza',
    '2_Pogoda',
    '3_Pogoda_Slonce',
    '3_Pogoda_Slonce_Reguly',
]

PHASE_LABELS = {
    '1_Baza': 'Baza',
    '2_Pogoda': 'Pogoda',
    '3_Pogoda_Slonce': 'Pogoda + Słońce',
    '3_Pogoda_Slonce_Reguly': '★ Wdrożone (16 cech)',
}

OUTPUT_SCATTER = 'reports/figures/academic_scatter_actual_vs_pred.png'
OUTPUT_ERRORS = 'reports/figures/academic_errors_mae_rmse.png'
OUTPUT_METRICS = 'data/processed/academic_evaluation_metrics.csv'

COLORS = {
    'scatter': '#2c5282',
    'scatter_prod': '#276749',
    'diagonal': '#c53030',
    'mae': '#2b6cb0',
    'rmse': '#c05621',
}


def _phase_label(key: str) -> str:
    return PHASE_LABELS.get(key, key)


def evaluate_all_phases() -> tuple[pd.DataFrame, dict[str, tuple[np.ndarray, np.ndarray]]]:
    """Trenuj RF per faza; zwróć tabelę metryk i pary (y_true, y_pred)."""
    train_df, test_df = _load_and_split()
    y_true = test_df[TARGET_COLUMN].values

    rows = []
    predictions: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    for phase_key in ACADEMIC_PHASES:
        features = FEATURE_GROUPS[phase_key]
        model = RandomForestRegressor(
            n_estimators=N_ESTIMATORS,
            max_depth=MAX_DEPTH,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
        model.fit(train_df[features], train_df[TARGET_COLUMN])
        y_pred = model.predict(test_df[features])

        mae = mean_absolute_error(y_true, y_pred)
        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        r2 = r2_score(y_true, y_pred)

        rows.append({
            'Etap': phase_key,
            'Faza': _phase_label(phase_key),
            'N_cech': len(features),
            'Test_MAE': mae,
            'Test_RMSE': rmse,
            'Test_R2': r2,
        })
        predictions[phase_key] = (y_true.copy(), y_pred.copy())
        print(f'  {_phase_label(phase_key):18s}  MAE={mae:.3f}  RMSE={rmse:.3f}  R²={r2:.3f}')

    metrics = pd.DataFrame(rows)
    os.makedirs('data/processed', exist_ok=True)
    metrics.to_csv(OUTPUT_METRICS, index=False)
    print(f'✓ {OUTPUT_METRICS}')
    return metrics, predictions


def plot_scatter_grid(
    predictions: dict[str, tuple[np.ndarray, np.ndarray]],
    metrics: pd.DataFrame,
    out_path: str = OUTPUT_SCATTER,
) -> None:
    """Wykres 1: siatka 2×2 — rzeczywistość vs prognoza."""
    sns.set_theme(style='whitegrid', context='paper', font_scale=1.05)
    fig, axes = plt.subplots(2, 2, figsize=(11, 10), constrained_layout=True)
    axes_flat = axes.flatten()

    all_y = np.concatenate([predictions[k][0] for k in ACADEMIC_PHASES])
    all_pred = np.concatenate([predictions[k][1] for k in ACADEMIC_PHASES])
    lim_lo = 0.0
    lim_hi = max(all_y.max(), all_pred.max()) * 1.05

    prod_key = ACADEMIC_PHASES[-1]

    for ax, phase_key in zip(axes_flat, ACADEMIC_PHASES):
        y_true, y_pred = predictions[phase_key]
        r2 = metrics.loc[metrics['Etap'] == phase_key, 'Test_R2'].iloc[0]
        label = _phase_label(phase_key)
        color = COLORS['scatter_prod'] if phase_key == prod_key else COLORS['scatter']

        ax.scatter(
            y_true, y_pred,
            alpha=0.45, s=18, c=color, edgecolors='none',
        )
        ax.plot(
            [lim_lo, lim_hi], [lim_lo, lim_hi],
            color=COLORS['diagonal'], linewidth=1.8, linestyle='--',
        )
        ax.set_xlim(lim_lo, lim_hi)
        ax.set_ylim(lim_lo, lim_hi)
        ax.set_aspect('equal', adjustable='box')
        ax.set_title(f'{label}\n$R^2$ = {r2:.3f}', fontsize=12, fontweight='semibold')
        ax.set_xlabel('Rzeczywista produkcja PV [kWh/h]')
        ax.set_ylabel('Prognozowana produkcja PV [kWh/h]')

    fig.suptitle(
        'Ewaluacja regresji RF: rzeczywistość vs prognoza (split 80/20, 2025-06 → 2026-05)',
        fontsize=14, fontweight='bold', y=1.02,
    )
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'✓ {out_path}')


def plot_error_decline(
    metrics: pd.DataFrame,
    out_path: str = OUTPUT_ERRORS,
) -> None:
    """Wykres 2: spadek MAE i RMSE między fazami."""
    sns.set_theme(style='whitegrid', context='paper', font_scale=1.05)
    fig, ax = plt.subplots(figsize=(10, 6))

    x = np.arange(len(metrics))
    width = 0.35

    bars_mae = ax.bar(
        x - width / 2, metrics['Test_MAE'], width,
        label='MAE', color=COLORS['mae'], alpha=0.88, edgecolor='white',
    )
    bars_rmse = ax.bar(
        x + width / 2, metrics['Test_RMSE'], width,
        label='RMSE', color=COLORS['rmse'], alpha=0.88, edgecolor='white',
    )

    ax.plot(x, metrics['Test_MAE'], color=COLORS['mae'], marker='o', linewidth=2, markersize=7, zorder=5)
    ax.plot(x, metrics['Test_RMSE'], color=COLORS['rmse'], marker='s', linewidth=2, markersize=7, zorder=5)

    for bar in list(bars_mae) + list(bars_rmse):
        h = bar.get_height()
        ax.annotate(
            f'{h:.2f}',
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 6),
            textcoords='offset points',
            ha='center', va='bottom', fontsize=9, fontweight='medium',
        )

    ax.set_xticks(x)
    ax.set_xticklabels(metrics['Faza'], fontsize=10)
    ax.set_ylabel('Błąd [kWh/h]')
    ax.set_xlabel('Faza inżynierii cech')
    ax.set_title(
        'Spadek błędu predykcji w kolejnych fazach (MAE / RMSE)',
        fontsize=13, fontweight='bold', pad=12,
    )
    ax.legend(loc='upper right', framealpha=0.95)
    ax.grid(True, axis='y', linestyle='--', alpha=0.6)
    ax.set_axisbelow(True)

    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'✓ {out_path}')


def main() -> None:
    print('=' * 60)
    print('WYKRESY AKADEMICKIE — 4 fazy (ścieżka produkcyjna)')
    print('=' * 60)
    print('Fazy:', ' → '.join(_phase_label(p) for p in ACADEMIC_PHASES))
    print(f'RF: n_estimators={N_ESTIMATORS}, max_depth={MAX_DEPTH}, random_state={RANDOM_STATE}')
    print('\n[1] Trening i metryki per faza...')
    metrics, predictions = evaluate_all_phases()

    print('\n[2] Wykres scatter (rzeczywistość vs prognoza)...')
    plot_scatter_grid(predictions, metrics)

    print('\n[3] Wykres spadku błędu (MAE / RMSE)...')
    plot_error_decline(metrics)

    print('\n' + '=' * 60)
    print('GOTOWE')
    print('=' * 60)


if __name__ == '__main__':
    main()
