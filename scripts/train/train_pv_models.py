"""
Trening prostych modeli regresji PV (target: pv_kwh_daytime).

UWAGA: pv_kwh_daytime to suma PV w godzinach wschód–zachód (dynamicznie).
       Filtr baterii (battery_power >= -0.1) stosowany przy odczycie.
       Dla harmonogramów godzinowych użyj train_hourly_model.py.

Modele: Ridge, Random Forest, XGBoost, MLP (2 architektury) + RF z korektą reguł.

Strategia podziału (wszystkie sezony w train i test, ekstrema w train):
    TRAIN: 2025-06-01 do 2026-01-31 (lato, jesień, zima -3.7°C) — 8 miesięcy
    TEST:  2026-02-01 do dziś (zima -0.4°C, wiosna, lato) — 7 miesięcy

Uruchomienie:
    python scripts/train_pv_models.py
    python scripts/train_pv_models.py --test-start 2026-02-01
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv()

from src.data.photo_ground_truth import PV_CORRECTION_FACTOR
from src.data.weather_api import apply_pv_rule_correction, winter_reference_yield
from src.features.pv_features import (
    DEFAULT_SNOW_THAW_TEMP_C,
    DEFAULT_SNOW_WINDOW_DAYS,
    FEATURE_COLUMNS,
    apply_snow_panel_flags,
    calibrate_snow_panel_params,
    load_training_frame,
    time_train_test_split,
)

try:
    from xgboost import XGBRegressor
except ImportError:  # pragma: no cover
    XGBRegressor = None


def _metrics(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mape_mask = y_true > 0.5
    mape = (
        float(np.mean(np.abs((y_true[mape_mask] - y_pred[mape_mask]) / y_true[mape_mask])) * 100)
        if mape_mask.any()
        else float('nan')
    )
    return {
        'mae_kwh': float(mean_absolute_error(y_true, y_pred)),
        'rmse_kwh': float(np.sqrt(mean_squared_error(y_true, y_pred))),
        'r2': float(r2_score(y_true, y_pred)),
        'mape_pct': mape,
    }


def _baseline_radiation(
    X_test: pd.DataFrame,
    train_part: pd.DataFrame,
    target_col: str = 'pv_kwh_daytime',
    rad_col: str = 'radiation_daytime_kwh_m2',
) -> np.ndarray:
    """Baseline: radiacja 9–16 × mediana yield z train."""
    yield_med = (train_part[target_col] / train_part[rad_col].clip(lower=0.05)).median()
    return X_test[rad_col].values * yield_med


def _monthly_mae(pred_df: pd.DataFrame) -> pd.DataFrame:
    """MAE wg miesiąca dla każdego modelu."""
    df = pred_df.copy()
    df['month'] = pd.to_datetime(df['day']).dt.to_period('M').astype(str)
    rows = []
    for (model, month), grp in df.groupby(['model', 'month']):
        rows.append({
            'model': model,
            'month': month,
            'n_days': len(grp),
            'mae_kwh': float(mean_absolute_error(grp['y_true'], grp['y_pred'])),
            'mean_pv_kwh': float(grp['y_true'].mean()),
            'mean_pred_kwh': float(grp['y_pred'].mean()),
        })
    return pd.DataFrame(rows).sort_values(['month', 'mae_kwh'])


def _plot_monthly_mae(monthly: pd.DataFrame, out_path: str, focus_models: list[str]) -> None:
    """Wykres słupkowy MAE wg miesiąca (RF vs RF+reguły)."""
    plot_df = monthly[monthly['model'].isin(focus_models)].copy()
    if plot_df.empty:
        return

    months = sorted(plot_df['month'].unique())
    x = np.arange(len(months))
    width = 0.35
    labels = {
        'random_forest': 'Random Forest',
        'random_forest_rules': 'RF + reguły',
    }

    fig, ax = plt.subplots(figsize=(11, 5))
    for i, model in enumerate(focus_models):
        sub = plot_df[plot_df['model'] == model].set_index('month').reindex(months)
        offset = (i - (len(focus_models) - 1) / 2) * width
        ax.bar(
            x + offset,
            sub['mae_kwh'],
            width=width,
            label=labels.get(model, model),
        )

    ax.set_xticks(x)
    ax.set_xticklabels(months, rotation=45, ha='right')
    ax.set_ylabel('MAE [kWh]')
    ax.set_title('Błąd predykcji PV wg miesiąca (zbiór testowy)')
    ax.legend()
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _winter_ref_yield(train_part: pd.DataFrame) -> float:
    """Referencyjny yield zimą; fallback na medianę yield z train."""
    weather_cols = [
        'day', 'cloud_cover_avg', 'radiation_daytime_kwh_m2',
    ]
    weather = train_part[weather_cols].copy()
    weather['radiation_kwh_m2'] = weather['radiation_daytime_kwh_m2']
    pv_day = train_part[['day', 'pv_kwh_daytime']].copy()
    pv = train_part[['day', 'pv_kwh_artifact']].copy()
    try:
        ref = winter_reference_yield(weather, pv_day, pv)
    except Exception:
        ref = float('nan')
    if pd.isna(ref) or ref <= 0:
        rad = train_part['radiation_daytime_kwh_m2'].clip(lower=0.05)
        ref = float((train_part['pv_kwh_daytime'] / rad).median())
    return ref


def get_models() -> dict[str, Any]:
    models: dict[str, Any] = {
        'ridge_linear': Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler()),
            ('model', Ridge(alpha=1.0)),
        ]),
        'random_forest': Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('model', RandomForestRegressor(
                n_estimators=200, max_depth=12, min_samples_leaf=2, random_state=42, n_jobs=-1,
            )),
        ]),
        # MLP modele wyłączone - powodują błędy numeryczne (overflow) z nowymi danymi
        # 'mlp_shallow': Pipeline([
        #     ('imputer', SimpleImputer(strategy='median')),
        #     ('scaler', StandardScaler()),
        #     ('model', MLPRegressor(
        #         hidden_layer_sizes=(32, 16), max_iter=800, random_state=42,
        #         early_stopping=True, validation_fraction=0.15,
        #     )),
        # ]),
        # 'mlp_deep': Pipeline([
        #     ('imputer', SimpleImputer(strategy='median')),
        #     ('scaler', StandardScaler()),
        #     ('model', MLPRegressor(
        #         hidden_layer_sizes=(64, 32, 16), max_iter=1000, random_state=42,
        #         early_stopping=True, validation_fraction=0.15, alpha=1e-4,
        #     )),
        # ]),
    }
    if XGBRegressor is not None:
        models['xgboost'] = Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('model', XGBRegressor(
                n_estimators=300, max_depth=5, learning_rate=0.08,
                subsample=0.9, colsample_bytree=0.9, random_state=42,
                objective='reg:squarederror', n_jobs=-1,
            )),
        ])
    return models


def main() -> None:
    parser = argparse.ArgumentParser(description='Trening modeli regresji PV (dzienny, agregacja historyczna)')
    parser.add_argument('--test-start', default=os.getenv('ML_TEST_START', '2026-02-01'))
    parser.add_argument(
        '--snow-window-days',
        type=int,
        default=None,
        help=f'Okno śniegu na panelach [dni]. Domyślnie: {DEFAULT_SNOW_WINDOW_DAYS} lub SNOW_WINDOW_DAYS z .env',
    )
    parser.add_argument(
        '--snow-thaw-temp',
        type=float,
        default=None,
        help=f'Próg odwilży [°C]. Domyślnie: {DEFAULT_SNOW_THAW_TEMP_C} lub SNOW_THAW_TEMP_C z .env',
    )
    parser.add_argument(
        '--snow-auto-calibrate',
        action='store_true',
        help='Dobierz okno/próg śniegu automatycznie (CV na zbiorze train, przed test_start).',
    )
    parser.add_argument(
        '--csv',
        default=os.getenv('ML_RESULTS_CSV', 'data/processed/model_comparison.csv'),
    )
    parser.add_argument(
        '--predictions-csv',
        default=os.getenv('ML_PREDICTIONS_CSV', 'data/processed/model_predictions.csv'),
    )
    parser.add_argument(
        '--monthly-csv',
        default=os.getenv('ML_MONTHLY_CSV', 'data/processed/monthly_mae.csv'),
    )
    parser.add_argument(
        '--monthly-plot',
        default=os.getenv('ML_MONTHLY_PLOT', 'reports/figures/monthly_mae.png'),
    )
    args = parser.parse_args()

    print('=' * 72)
    print('Regresja PV DZIENNA — porównanie modeli (walidacja czasowa)')
    print('UWAGA: target pv_kwh_daytime = suma PV w godzinach wschód–zachód (dynamicznie)')
    print('=' * 72)

    snow_window = args.snow_window_days
    snow_thaw = args.snow_thaw_temp
    snow_ranking = None

    if args.snow_auto_calibrate:
        base_frame = load_training_frame()
        snow_window, snow_thaw, snow_ranking = calibrate_snow_panel_params(
            base_frame, train_end=args.test_start,
        )
        frame = apply_snow_panel_flags(base_frame, snow_window, snow_thaw)
        print(f'❄️ Auto-kalibracja śniegu: okno={snow_window} dni, odwilż={snow_thaw}°C')
        print(snow_ranking.head(5).to_string(index=False, float_format=lambda x: f'{x:.3f}'))
    else:
        snow_window = snow_window or int(os.getenv('SNOW_WINDOW_DAYS', str(DEFAULT_SNOW_WINDOW_DAYS)))
        snow_thaw = snow_thaw if snow_thaw is not None else float(
            os.getenv('SNOW_THAW_TEMP_C', str(DEFAULT_SNOW_THAW_TEMP_C))
        )
        frame = load_training_frame(snow_window_days=snow_window, snow_thaw_temp_c=snow_thaw)
        print(f'❄️ Parametry śniegu: okno={snow_window} dni, odwilż={snow_thaw}°C')

    split = time_train_test_split(frame, test_start=args.test_start)
    print(f'Dni train: {len(split.y_train)} | test: {len(split.y_test)} (od {split.test_start})')

    train_part = frame[frame['day'] < args.test_start]
    test_part = frame[frame['day'] >= args.test_start].reset_index(drop=True)
    rule_cols = FEATURE_COLUMNS + ['day']
    rule_rows = test_part[[c for c in rule_cols if c in test_part.columns]].copy()
    ref_yield = _winter_ref_yield(train_part)

    rows = []
    pred_frames = []

    baseline_pred = _baseline_radiation(split.X_test, train_part)
    base_m = _metrics(split.y_test, baseline_pred)
    rows.append({'model': 'baseline_radiation_yield', **base_m})
    pred_frames.append(pd.DataFrame({
        'day': split.meta_test['day'].values,
        'model': 'baseline_radiation_yield',
        'y_true': split.y_test.values,
        'y_pred': baseline_pred,
    }))

    rf_pred: np.ndarray | None = None

    for name, model in get_models().items():
        print(f'Trenuję: {name}...')
        model.fit(split.X_train, split.y_train)
        pred = model.predict(split.X_test)
        m = _metrics(split.y_test, pred)
        rows.append({'model': name, **m})
        pred_frames.append(pd.DataFrame({
            'day': split.meta_test['day'].values,
            'model': name,
            'y_true': split.y_test.values,
            'y_pred': pred,
        }))
        if name == 'random_forest':
            rf_pred = pred

    if rf_pred is not None:
        print('Korekta: random_forest + reguły pogodowe...')
        rf_rules_pred = apply_pv_rule_correction(
            rf_pred,
            rule_rows,
            ref_yield_kwh_per_kwh_m2=ref_yield,
            correction_factors=PV_CORRECTION_FACTOR,
        )
        rules_m = _metrics(split.y_test, rf_rules_pred)
        rows.append({'model': 'random_forest_rules', **rules_m})
        pred_frames.append(pd.DataFrame({
            'day': split.meta_test['day'].values,
            'model': 'random_forest_rules',
            'y_true': split.y_test.values,
            'y_pred': rf_rules_pred,
        }))

    results = pd.DataFrame(rows).sort_values('mae_kwh')
    all_preds = pd.concat(pred_frames, ignore_index=True)
    monthly = _monthly_mae(all_preds)

    print('\nWyniki (posortowane wg MAE):')
    print(results.to_string(index=False, float_format=lambda x: f'{x:.3f}'))

    print('\nMAE wg miesiąca (RF vs RF+reguły):')
    focus = monthly[monthly['model'].isin(['random_forest', 'random_forest_rules'])]
    if not focus.empty:
        print(focus.to_string(index=False, float_format=lambda x: f'{x:.3f}'))

    os.makedirs(os.path.dirname(args.csv) or '.', exist_ok=True)
    results.to_csv(args.csv, index=False)
    all_preds.to_csv(args.predictions_csv, index=False)
    monthly.to_csv(args.monthly_csv, index=False)
    _plot_monthly_mae(monthly, args.monthly_plot, ['random_forest', 'random_forest_rules'])

    print(f'\n✅ Zapisano: {args.csv}')
    print(f'✅ Predykcje: {args.predictions_csv}')
    print(f'✅ MAE miesięczne: {args.monthly_csv}')
    print(f'✅ Wykres MAE: {args.monthly_plot}')
    print('\n💡 Następny krok: notebook notebooks/02_ML_predykcja_PV.ipynb (wykresy)')


if __name__ == '__main__':
    main()
