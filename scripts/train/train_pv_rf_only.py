#!/usr/bin/env python
"""Trening Random Forest PV - bez problemów ze skalowaniem."""
import os
os.environ['ML_TRAIN_START'] = '2025-06-01'
os.environ['ML_TEST_START'] = '2026-02-01'

import sys
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.features.pv_features import load_training_frame, time_train_test_split
from src.data.photo_ground_truth import PV_CORRECTION_FACTOR
from src.data.weather_api import apply_pv_rule_correction, winter_reference_yield
from src.features.pv_features import FEATURE_COLUMNS

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

print('=' * 72)
print('Trening Random Forest PV (nowy podział 2025-06 / 2026-02)')
print('=' * 72)

frame = load_training_frame()
split = time_train_test_split(frame)

print(f'\nDane: {len(frame)} dni ({frame["day"].min()} → {frame["day"].max()})')
print(f'Train: {len(split.y_train)} dni (2025-06 → 2026-01)')
print(f'Test:  {len(split.y_test)} dni (2026-02 → 2026-06)')

# Baseline
def _baseline_radiation(X_test, train_part, target_col='pv_kwh_daytime', rad_col='radiation_daytime_kwh_m2'):
    yield_med = (train_part[target_col] / train_part[rad_col].clip(lower=0.05)).median()
    return X_test[rad_col].values * yield_med

train_part = frame[frame['day'] < '2026-02-01']
test_part = frame[frame['day'] >= '2026-02-01'].reset_index(drop=True)

baseline_pred = _baseline_radiation(split.X_test, train_part)
base_m = _metrics(split.y_test, baseline_pred)

print(f'\n[Baseline] Radiation × yield')
print(f'  MAE: {base_m["mae_kwh"]:.3f} kWh | RMSE: {base_m["rmse_kwh"]:.3f} | R²: {base_m["r2"]:.3f}')

# Random Forest
print(f'\n[1] Random Forest (n=200, depth=12)')
model_rf = Pipeline([
    ('imputer', SimpleImputer(strategy='median')),
    ('model', RandomForestRegressor(
        n_estimators=200, max_depth=12, min_samples_leaf=2, 
        random_state=42, n_jobs=-1
    )),
])

model_rf.fit(split.X_train, split.y_train)
train_pred = model_rf.predict(split.X_train)
test_pred = model_rf.predict(split.X_test)

train_m = _metrics(split.y_train, train_pred)
test_m = _metrics(split.y_test, test_pred)
gap = test_m['mae_kwh'] - train_m['mae_kwh']

print(f'  Train MAE: {train_m["mae_kwh"]:.3f} kWh | RMSE: {train_m["rmse_kwh"]:.3f} | R²: {train_m["r2"]:.3f}')
print(f'  Test MAE:  {test_m["mae_kwh"]:.3f} kWh | RMSE: {test_m["rmse_kwh"]:.3f} | R²: {test_m["r2"]:.3f}')
print(f'  Gap:       {gap:.3f} kWh ({gap/test_m["mae_kwh"]*100:.1f}%)')

# Top 10 najważniejszych cech
rf = model_rf.named_steps['model']
print('\n[Top 10 cech Random Forest]')
importances = rf.feature_importances_
feature_importance = pd.DataFrame({
    'feature': split.X_train.columns,
    'importance': importances
}).sort_values('importance', ascending=False)
print(feature_importance.head(10).to_string(index=False))

# Sprawdź flagi mgły i śniegu
fog_snow = feature_importance[feature_importance['feature'].str.contains('fog|snow')]
if not fog_snow.empty:
    print('\n[Flagi mgły i śniegu]')
    print(fog_snow.to_string(index=False))

# RF + reguły pogodowe
print(f'\n[2] Random Forest + reguły pogodowe')
rule_cols = FEATURE_COLUMNS + ['day']
rule_rows = test_part[[c for c in rule_cols if c in test_part.columns]].copy()

def _winter_ref_yield(train_part):
    weather_cols = ['day', 'cloud_cover_avg', 'radiation_daytime_kwh_m2']
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

ref_yield = _winter_ref_yield(train_part)
rf_rules_pred = apply_pv_rule_correction(
    test_pred, rule_rows,
    ref_yield_kwh_per_kwh_m2=ref_yield,
    correction_factors=PV_CORRECTION_FACTOR,
)

rules_m = _metrics(split.y_test, rf_rules_pred)
gap_rules = rules_m['mae_kwh'] - train_m['mae_kwh']

print(f'  Test MAE:  {rules_m["mae_kwh"]:.3f} kWh | RMSE: {rules_m["rmse_kwh"]:.3f} | R²: {rules_m["r2"]:.3f}')
print(f'  Gap:       {gap_rules:.3f} kWh ({gap_rules/rules_m["mae_kwh"]*100:.1f}%)')

# Podsumowanie
print('\n' + '=' * 72)
print('PODSUMOWANIE')
print('=' * 72)

results = pd.DataFrame([
    {'model': 'baseline_radiation_yield', **base_m},
    {'model': 'random_forest', **test_m},
    {'model': 'random_forest_rules', **rules_m},
]).sort_values('mae_kwh')

print(results[['model', 'mae_kwh', 'rmse_kwh', 'r2']].to_string(index=False, float_format=lambda x: f'{x:.3f}'))

# Zapis
os.makedirs('data/processed', exist_ok=True)
results.to_csv('data/processed/model_comparison.csv', index=False)
print(f'\n✅ Wyniki zapisane: data/processed/model_comparison.csv')
