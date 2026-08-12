#!/usr/bin/env python
"""
Wykres szeregów czasowych: prognoza vs rzeczywista PV.

Dwa panele OBOK SIEBIE (osobne okna czasu — bez wspólnej osi):
  • LEWY  — TYLKO TRAIN / in-sample  (< 2026-06-01)
  • PRAWY — TYLKO HOLDOUT / OOS      (≥ 2026-06-01) — tu ocena + ★ RF .joblib

- Źródło: SQLite (load_training_frame) — NIE cache CSV
- Target: pv_kwh_daytime (filtr baterii + dynamiczne wschód–zachód)
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import joblib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from src.features.pv_features import TARGET_COLUMN, load_training_frame
from src.features.pv_features_hourly_extended import (
    load_hourly_training_frame_extended,
)
from src.data.household_context import PRODUCTION_HOLDOUT_START
from src.models.pv_hourly_predictor import (
    DEFAULT_MODEL_PATH,
    RF_MAX_DEPTH,
    RF_MAX_FEATURES,
    RF_MIN_SAMPLES_LEAF,
    RF_MIN_SAMPLES_SPLIT,
    RF_N_ESTIMATORS,
    RF_RANDOM_STATE,
    resolve_model_path,
)

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / 'data' / 'energy_model.db'
LOCATION = 'home'
# Oś pozioma od czerwca 2025 — jak okno modelu wdrożeniowego
START = '2025-06-01'
PROD_START = PRODUCTION_HOLDOUT_START.isoformat()  # 2026-06-01


def _default_end() -> str:
    return date.today().isoformat()


def _production_rf(**extra) -> RandomForestRegressor:
    return RandomForestRegressor(
        n_estimators=RF_N_ESTIMATORS,
        max_depth=RF_MAX_DEPTH,
        min_samples_leaf=RF_MIN_SAMPLES_LEAF,
        min_samples_split=RF_MIN_SAMPLES_SPLIT,
        max_features=RF_MAX_FEATURES,
        random_state=RF_RANDOM_STATE,
        n_jobs=-1,
        **extra,
    )


def _plot_with_gap_breaks(ax, dates, values, **kwargs) -> None:
    s = pd.DataFrame({'date': pd.to_datetime(dates), 'y': values}).sort_values('date')
    gap = s['date'].diff().dt.days.fillna(1) > 1
    s.loc[gap, 'y'] = np.nan
    ax.plot(s['date'], s['y'], **kwargs)


def _hourly_production_daily(db_path: Path, end: str) -> pd.Series | None:
    """Agregacja dzienna predykcji z wdrożeniowego modelu godzinowego (.joblib)."""
    model_path = Path(resolve_model_path())
    if not model_path.exists():
        return None
    data = joblib.load(model_path)
    pipeline = data['pipeline']
    feature_columns = data.get('feature_columns', [])
    lat = float(data.get('latitude') or os.getenv('WEATHER_LAT', '50.06'))
    lon = float(data.get('longitude') or os.getenv('WEATHER_LON', '19.94'))

    hourly = load_hourly_training_frame_extended(
        str(db_path), START, end, LOCATION, latitude=lat, longitude=lon,
    )
    if hourly.empty or not feature_columns:
        return None
    X = hourly[feature_columns]
    hourly = hourly.copy()
    hourly['pred_hourly_prod'] = np.clip(pipeline.predict(X), 0, None)
    return hourly.groupby('day')['pred_hourly_prod'].sum()


def build_chart(
    db_path: Path | str = DB_PATH,
    end: str | None = None,
    save_paths: list[Path] | None = None,
    show: bool = False,
) -> pd.DataFrame:
    end = end or _default_end()
    db_path = Path(db_path)

    print('=' * 72)
    print('Wykres: Prognoza vs PV (protokół wdrożeniowy)')
    print(f'Baza: {db_path}  |  Zakres osi X: {START} → {end}')
    print(f'Target: {TARGET_COLUMN}')
    print(f'RF prod. params: max_depth={RF_MAX_DEPTH}, leaf={RF_MIN_SAMPLES_LEAF}')
    print('=' * 72)

    df = load_training_frame(str(db_path), START, end, LOCATION)
    df = df.sort_values('day').reset_index(drop=True)
    print(f'\nDni w ramce: {len(df)}  ({df["day"].min()} → {df["day"].max()})')

    # Trening modeli dziennych (porównanie) na okresie przed holdoutem czerwiec 2026
    train_df = df[df['day'] < PROD_START].copy()
    all_for_pred = df.copy()

    BASELINE_FEATURES = [
        'radiation_daytime_kwh_m2', 'cloud_cover_avg', 'cloud_cover_low_avg',
        'temp_avg', 'temp_min', 'temp_max', 'humidity_daytime_avg',
        'precip_mm', 'om_snowfall_cm', 'om_snow_depth_cm', 'imgw_snow_depth_cm',
        'day_length_hours', 'doy_sin', 'doy_cos', 'month',
    ]
    CALIBRATED_FEATURES = BASELINE_FEATURES + [
        'snow_on_panels', 'snow_on_panels_prev', 'likely_fog_day', 'rainy_day',
    ]

    X_base_tr = train_df[BASELINE_FEATURES].fillna(0)
    X_cal_tr = train_df[CALIBRATED_FEATURES].fillna(0)
    y_tr = train_df[TARGET_COLUMN]

    rf_legacy = RandomForestRegressor(n_estimators=200, max_depth=12, random_state=42, n_jobs=-1)
    rf_legacy.fit(X_base_tr, y_tr)

    rf_prod_daily = _production_rf()
    rf_prod_daily.fit(X_cal_tr, y_tr)

    scaler = StandardScaler()
    X_cal_sc = scaler.fit_transform(X_cal_tr)
    ridge = Ridge(alpha=10.0, random_state=42)
    ridge.fit(X_cal_sc, y_tr)

    xgb = XGBRegressor(n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1)
    xgb.fit(X_cal_tr, y_tr)

    all_for_pred['pred_rf_legacy'] = rf_legacy.predict(all_for_pred[BASELINE_FEATURES].fillna(0))
    all_for_pred['pred_rf_production'] = rf_prod_daily.predict(all_for_pred[CALIBRATED_FEATURES].fillna(0))
    all_for_pred['pred_ridge'] = ridge.predict(scaler.transform(all_for_pred[CALIBRATED_FEATURES].fillna(0)))
    all_for_pred['pred_xgb'] = xgb.predict(all_for_pred[CALIBRATED_FEATURES].fillna(0))
    all_for_pred['date'] = pd.to_datetime(all_for_pred['day'])

    hourly_daily = _hourly_production_daily(db_path, end)
    if hourly_daily is not None:
        all_for_pred['pred_hourly_prod_daily'] = all_for_pred['day'].map(hourly_daily)
        print('✓ Predykcja z modelu wdrożeniowego godzinowego (.joblib → suma/dzień)')
    else:
        all_for_pred['pred_hourly_prod_daily'] = np.nan
        print('⚠️  Brak pv_hourly_model.joblib — pominięto linię godzinową')

    print('\nMAE [kWh/d] — UWAGA: „cały zakres” miesza train+test (legacy/XGB wyglądają fałszywie dobrze):')
    hold = all_for_pred['day'] >= PROD_START
    train_m = all_for_pred['day'] < PROD_START
    print(f'{"Model":32s} {"cały":>8s} {"train":>8s} {"holdout":>8s}')
    for name, col in [
        ('RF legacy (max_depth=12)', 'pred_rf_legacy'),
        ('RF dzienny (regularyzowany)', 'pred_rf_production'),
        ('★ RF godzinowy → dzień', 'pred_hourly_prod_daily'),
        ('XGBoost', 'pred_xgb'),
    ]:
        def _mae(mask):
            m = mask & all_for_pred[col].notna()
            if not m.any():
                return float('nan')
            return float(np.abs(all_for_pred.loc[m, TARGET_COLUMN] - all_for_pred.loc[m, col]).mean())
        print(f'{name:32s} {_mae(all_for_pred["day"].notna()):8.3f} {_mae(train_m):8.3f} {_mae(hold):8.3f}')
    print('Decyzja modelowa ≠ ten wydruk — patrz Test MAE 80/20 (kWh/h) w §6.')

    # Dwa panele OBOK SIEBIE: lewy = TYLKO train, prawy = TYLKO holdout.
    # Żadnej wspólnej osi czasu — to było źródło „mieszania” in-sample z OOS.
    before = all_for_pred[all_for_pred['day'] < PROD_START].copy()
    after = all_for_pred[all_for_pred['day'] >= PROD_START].copy()
    y_max = float(all_for_pred[TARGET_COLUMN].quantile(0.99) * 1.15)

    def _mae_panel(frame: pd.DataFrame, col: str) -> float | None:
        m = frame[col].notna() & frame[TARGET_COLUMN].notna()
        if not m.any():
            return None
        return float(np.abs(frame.loc[m, TARGET_COLUMN] - frame.loc[m, col]).mean())

    def _style_axes(ax_train, ax_hold) -> None:
        if not before.empty:
            ax_train.set_xlim(
                pd.to_datetime(START),
                pd.to_datetime(PROD_START) - pd.Timedelta(days=1),
            )
        if not after.empty:
            ax_hold.set_xlim(
                pd.to_datetime(PROD_START),
                pd.to_datetime(end) + pd.Timedelta(days=1),
            )
        for ax in (ax_train, ax_hold):
            ax.set_ylim(bottom=0, top=max(y_max, 5))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

    def _mae_box(ax, lines: list[str]) -> None:
        if not lines:
            return
        ax.text(
            0.99, 0.98, '\n'.join(lines), transform=ax.transAxes,
            ha='right', va='top', fontsize=9,
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.9),
        )

    def _draw_comparison_panel(
        ax,
        frame: pd.DataFrame,
        *,
        title: str,
        show_hourly_prod: bool,
        face: str,
    ) -> None:
        """Wykres 1 — porównanie wielu modeli."""
        ax.set_facecolor(face)
        if frame.empty:
            ax.text(0.5, 0.5, 'Brak danych w tym oknie', ha='center', va='center',
                    transform=ax.transAxes)
            ax.set_title(title, fontweight='bold', fontsize=11)
            return

        _plot_with_gap_breaks(
            ax, frame['date'], frame[TARGET_COLUMN],
            color='#1f77b4', linewidth=1.8, marker='o', markersize=3,
            label=f'Rzeczywiste ({TARGET_COLUMN})', zorder=5,
        )
        if show_hourly_prod:
            _plot_with_gap_breaks(
                ax, frame['date'], frame['pred_hourly_prod_daily'],
                color='#276749', linewidth=2.0, alpha=0.95,
                label='★ RF wdrożony godzinowy → dzień', zorder=4,
            )
        _plot_with_gap_breaks(
            ax, frame['date'], frame['pred_rf_production'],
            color='#2ca02c', linewidth=1.2, linestyle='--', alpha=0.8,
            label=f'RF dzienny (d={RF_MAX_DEPTH}, fit na train)', zorder=3,
        )
        _plot_with_gap_breaks(
            ax, frame['date'], frame['pred_rf_legacy'],
            color='#ff7f0e', linewidth=1.0, linestyle=':', alpha=0.55,
            label='RF legacy (fit na train)', zorder=2,
        )
        _plot_with_gap_breaks(
            ax, frame['date'], frame['pred_xgb'],
            color='#d62728', linewidth=0.9, linestyle=':', alpha=0.5,
            label='XGBoost (fit na train)', zorder=1,
        )

        ax.set_ylabel('Produkcja PV (kWh/dobę)')
        ax.set_xlabel('Data')
        ax.set_title(title, fontweight='bold', fontsize=11, pad=10)
        ax.grid(True, alpha=0.35)
        ax.legend(loc='upper left', fontsize=7.5, ncol=1, framealpha=0.95)

        bits = []
        if show_hourly_prod:
            mae_h = _mae_panel(frame, 'pred_hourly_prod_daily')
            if mae_h is not None:
                bits.append(f'★ RF godz. MAE={mae_h:.1f}')
        mae_r = _mae_panel(frame, 'pred_rf_production')
        mae_x = _mae_panel(frame, 'pred_xgb')
        if mae_r is not None:
            bits.append(f'RF dz. MAE={mae_r:.1f}')
        if mae_x is not None:
            bits.append(f'XGB MAE={mae_x:.1f}')
        _mae_box(ax, bits)

    def _draw_deployed_panel(
        ax,
        frame: pd.DataFrame,
        *,
        title: str,
        face: str,
    ) -> None:
        """Wykres 2 — tylko rzeczywistość + ★ RF wdrożony."""
        ax.set_facecolor(face)
        if frame.empty:
            ax.text(0.5, 0.5, 'Brak danych w tym oknie', ha='center', va='center',
                    transform=ax.transAxes)
            ax.set_title(title, fontweight='bold', fontsize=11)
            return

        _plot_with_gap_breaks(
            ax, frame['date'], frame[TARGET_COLUMN],
            color='#1f77b4', linewidth=2.0, marker='o', markersize=3.5,
            label='Rzeczywiste', zorder=5,
        )
        _plot_with_gap_breaks(
            ax, frame['date'], frame['pred_hourly_prod_daily'],
            color='#276749', linewidth=2.2, alpha=0.95,
            label='★ RF wdrożony (.joblib, 16 cech → dzień)', zorder=4,
        )
        ax.set_ylabel('Produkcja PV (kWh/dobę)')
        ax.set_xlabel('Data')
        ax.set_title(title, fontweight='bold', fontsize=11, pad=10)
        ax.grid(True, alpha=0.35)
        ax.legend(loc='upper left', fontsize=9, framealpha=0.95)
        mae_h = _mae_panel(frame, 'pred_hourly_prod_daily')
        if mae_h is not None:
            _mae_box(ax, [f'★ RF godz. MAE={mae_h:.1f} kWh/d'])

    # --- Figura 1: porównanie modeli ---
    fig1, (ax1_tr, ax1_ho) = plt.subplots(
        1, 2, figsize=(16, 6.5), sharey=True,
        gridspec_kw={'width_ratios': [1.35, 1.0]},
    )
    _draw_comparison_panel(
        ax1_tr, before,
        title=(
            f'TYLKO TRAIN / in-sample\n'
            f'{START} → dzień przed {PROD_START}\n'
            f'(tu XGB ≈ 0 = przeuczenie; NIE oceniamy operacyjnie)'
        ),
        show_hourly_prod=False,
        face='#f7f7f7',
    )
    _draw_comparison_panel(
        ax1_ho, after,
        title=(
            f'TYLKO HOLDOUT / out-of-sample\n'
            f'{PROD_START} → {end}\n'
            f'(tu oceniamy modele — w tym ★ RF wdrożony)'
        ),
        show_hourly_prod=True,
        face='#fff8f0',
    )
    _style_axes(ax1_tr, ax1_ho)
    fig1.suptitle(
        'Wykres 1 — porównanie modeli: TRAIN (lewy)  |  HOLDOUT (prawy)',
        fontsize=14, fontweight='bold', y=1.02,
    )
    fig1.autofmt_xdate(rotation=30, ha='right')
    fig1.tight_layout()

    if save_paths is None:
        save_paths = [
            ROOT / 'reports' / 'figures' / 'prediction_vs_actual_calibrated.png',
            ROOT / 'reports' / 'figures' / 'prediction_vs_actual_train_vs_holdout.png',
            ROOT / 'reports' / 'figures' / 'rf_vs_rules_timeseries.png',
        ]
    for p in save_paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        fig1.savefig(p, dpi=200, bbox_inches='tight')
        print(f'✓ Zapisano (wykres 1): {p}')

    # --- Figura 2: tylko model wdrożeniowy vs rzeczywistość ---
    fig2, (ax2_tr, ax2_ho) = plt.subplots(
        1, 2, figsize=(16, 6.5), sharey=True,
        gridspec_kw={'width_ratios': [1.35, 1.0]},
    )
    _draw_deployed_panel(
        ax2_tr, before,
        title=(
            f'TYLKO TRAIN\n'
            f'{START} → dzień przed {PROD_START}\n'
            f'(predykcje .joblib na okresie treningowym — nie gate operacyjny)'
        ),
        face='#f7f7f7',
    )
    _draw_deployed_panel(
        ax2_ho, after,
        title=(
            f'TYLKO HOLDOUT\n'
            f'{PROD_START} → {end}\n'
            f'(tu oceniamy ★ RF wdrożony vs rzeczywistość)'
        ),
        face='#fff8f0',
    )
    _style_axes(ax2_tr, ax2_ho)
    fig2.suptitle(
        'Wykres 2 — model wdrożeniowy vs rzeczywistość: TRAIN (lewy)  |  HOLDOUT (prawy)',
        fontsize=14, fontweight='bold', y=1.02,
    )
    fig2.autofmt_xdate(rotation=30, ha='right')
    fig2.tight_layout()

    deployed_paths = [
        ROOT / 'reports' / 'figures' / 'prediction_vs_actual_deployed_train_vs_holdout.png',
    ]
    for p in deployed_paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        fig2.savefig(p, dpi=200, bbox_inches='tight')
        print(f'✓ Zapisano (wykres 2): {p}')

    if show:
        plt.show()
    else:
        plt.close(fig1)
        plt.close(fig2)

    return all_for_pred


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    _db = os.getenv('DATABASE_PATH', str(DB_PATH))
    if not os.path.isabs(_db):
        _db = str(ROOT / _db)
    build_chart(db_path=_db, show=False)
