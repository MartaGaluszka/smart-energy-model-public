#!/usr/bin/env python
"""
Porównanie modeli PV dziennych — ewaluacja jak model wdrożeniowy.

Protokół (jak produkcja godzinowa):
  - zbiór 2025-06-01 → ostatni dostępny dzień
  - split 80/20 losowo po dniach (random_state=42)
  - jeden Test MAE / R² dla całego holdoutu (nie per miesiąc)

Sekcja „wpływ etykiet” też raportuje ΔMAE na całym teście.
Wykres miesięczny zostaje jako podgląd diagnostyczny.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

from src.data.household_context import FOXESS_RELIABLE_START, development_date_range
from src.features.pv_features import load_training_frame

RANDOM_STATE = 42
TRAIN_START = FOXESS_RELIABLE_START.isoformat()  # 2025-06-01
_, DATA_END = development_date_range()
# Do końca danych (holdout chronologiczny był legacy; tu: cały zakres + shuffle)
DATA_END = max(DATA_END, '2026-07-16')

DB_PATH = os.path.join(ROOT, 'data', 'energy_model.db')

print('=' * 80)
print('PORÓWNANIE MODELI — EWALUACJA JAK WDROŻENIE (80/20 po dniach)')
print('=' * 80)

# ============================================================================
# 1. Dane
# ============================================================================
print('\n1. Wczytanie danych...')
df = load_training_frame(DB_PATH, TRAIN_START, DATA_END, 'home')
df['month_name'] = pd.to_datetime(df['day']).dt.strftime('%Y-%m')
print(f'  Zakres: {df["day"].min()} → {df["day"].max()}  ({len(df)} dni)')

unique_days = df['day'].unique()
train_days, test_days = train_test_split(
    unique_days, test_size=0.2, random_state=RANDOM_STATE, shuffle=True,
)
train_df = df[df['day'].isin(train_days)].copy()
test_df = df[df['day'].isin(test_days)].copy()
print(f'  Split 80/20 po dniach (random_state={RANDOM_STATE}):')
print(f'    Train: {len(train_df)} dni | Test: {len(test_df)} dni')

# ============================================================================
# 2. Cechy
# ============================================================================
print('\n2. Zestawy cech...')
full_features = [
    'radiation_daytime_kwh_m2', 'cloud_cover_avg', 'cloud_cover_low_avg',
    'temp_avg', 'temp_min', 'temp_max', 'humidity_daytime_avg',
    'precip_mm', 'om_snowfall_cm', 'om_snow_depth_cm', 'imgw_snow_depth_cm',
    'snow_on_panels', 'snow_on_panels_prev',
    'likely_fog_day', 'rainy_day',
    'day_length_hours',
    'doy_sin', 'doy_cos', 'month',
]
baseline_features = [
    'radiation_daytime_kwh_m2', 'cloud_cover_avg', 'cloud_cover_low_avg',
    'temp_avg', 'temp_min', 'temp_max', 'humidity_daytime_avg',
    'precip_mm', 'om_snowfall_cm', 'om_snow_depth_cm', 'imgw_snow_depth_cm',
    'day_length_hours',
    'doy_sin', 'doy_cos', 'month',
]
target = 'pv_kwh'

# ============================================================================
# 3. Trening (tylko dni train)
# ============================================================================
print('\n3. Trening modeli (na train 80%)...')
X_full_tr = train_df[full_features].fillna(0)
X_base_tr = train_df[baseline_features].fillna(0)
y_tr = train_df[target]

rf_full = RandomForestRegressor(n_estimators=200, max_depth=12, random_state=42, n_jobs=-1)
rf_full.fit(X_full_tr, y_tr)
print('  [1/3] RF z etykietami...')

rf_baseline = RandomForestRegressor(n_estimators=200, max_depth=12, random_state=42, n_jobs=-1)
rf_baseline.fit(X_base_tr, y_tr)
print('  [2/3] RF bez etykiet...')

xgb = XGBRegressor(n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1)
xgb.fit(X_full_tr, y_tr)
print('  [3/3] XGBoost...')

# ============================================================================
# 4. Predykcje na TEŚCIE (jeden błąd dla całego zbioru)
# ============================================================================
print('\n4. Predykcje na teście...')
test_df = test_df.copy()
test_df['pred_rf_full'] = rf_full.predict(test_df[full_features].fillna(0))
test_df['pred_rf_baseline'] = rf_baseline.predict(test_df[baseline_features].fillna(0))
test_df['pred_xgb'] = xgb.predict(test_df[full_features].fillna(0))

# Też na train (diagnostyka gap)
train_df = train_df.copy()
train_df['pred_rf_full'] = rf_full.predict(X_full_tr)
train_df['pred_rf_baseline'] = rf_baseline.predict(X_base_tr)
train_df['pred_xgb'] = xgb.predict(X_full_tr)

models = {
    'RF z etykietami (fog, rain, snow)': 'pred_rf_full',
    'RF bez etykiet (baseline)': 'pred_rf_baseline',
    'XGBoost': 'pred_xgb',
}

# ============================================================================
# 5. Metryki ogólne — jak wdrożenie
# ============================================================================
print('\n5. Metryki CAŁEGO zbioru testowego (jak model wdrożeniowy):')
print(f'{"Model":45s} {"Train MAE":>10s} {"Test MAE":>10s} {"Gap":>8s} {"Test R²":>8s}')
print('-' * 85)

overall_rows = []
for name, col in models.items():
    train_mae = mean_absolute_error(train_df[target], train_df[col])
    test_mae = mean_absolute_error(test_df[target], test_df[col])
    test_r2 = r2_score(test_df[target], test_df[col])
    gap = test_mae - train_mae
    print(f'{name:45s} {train_mae:10.3f} {test_mae:10.3f} {gap:8.3f} {test_r2:8.3f}')
    overall_rows.append({
        'model': name,
        'train_mae': train_mae,
        'test_mae': test_mae,
        'gap': gap,
        'test_r2': test_r2,
        'n_train': len(train_df),
        'n_test': len(test_df),
    })

overall_df = pd.DataFrame(overall_rows)
overall_csv = os.path.join(ROOT, 'data', 'processed', 'daily_model_overall_metrics.csv')
os.makedirs(os.path.dirname(overall_csv), exist_ok=True)
overall_df.to_csv(overall_csv, index=False)
print(f'✓ {overall_csv}')

# ============================================================================
# 6. Wpływ etykiet — JEDEN wynik na całym teście
# ============================================================================
print('\n6. Wpływ etykiet (fog, rain, snow) — cały test:')
print('-' * 65)

mae_with = mean_absolute_error(test_df[target], test_df['pred_rf_full'])
mae_without = mean_absolute_error(test_df[target], test_df['pred_rf_baseline'])
delta = mae_without - mae_with  # >0 ⇒ etykiety pomagają
pct = (delta / mae_without) * 100 if mae_without > 0 else 0.0

label_mask = (
    (test_df['snow_on_panels'] == 1)
    | (test_df['likely_fog_day'] == 1)
    | (test_df['rainy_day'] == 1)
)
n_labeled = int(label_mask.sum())

status = '✅ pomagają' if delta > 0.02 else ('≈ remis' if abs(delta) <= 0.02 else '⚠️  pogarszają')
print(f'  RF z etykietami:   Test MAE = {mae_with:.3f} kWh/dzień')
print(f'  RF bez etykiet:    Test MAE = {mae_without:.3f} kWh/dzień')
print(f'  ΔMAE (bez − z):    {delta:+.3f} kWh/dzień  ({pct:+.1f}%)  → {status}')
print(f'  Dni z etykietą w teście: {n_labeled}/{len(test_df)}')

# ============================================================================
# 7. Wykres słupkowy — jeden błąd na model (jak wdrożenie)
# ============================================================================
print('\n7. Wykres Test MAE (cały zbiór)...')
sns.set_style('whitegrid')
fig, ax = plt.subplots(figsize=(10, 5))
colors = ['#276749', '#e74c3c', '#f39c12']
bars = ax.bar(overall_df['model'], overall_df['test_mae'], color=colors, edgecolor='white')
for bar, mae in zip(bars, overall_df['test_mae']):
    ax.annotate(
        f'{mae:.3f}',
        xy=(bar.get_x() + bar.get_width() / 2, mae),
        xytext=(0, 5), textcoords='offset points', ha='center', fontsize=10, fontweight='bold',
    )
ax.set_ylabel('Test MAE [kWh/dzień]')
ax.set_title(
    f'Porównanie modeli dziennych — Test MAE (split 80/20 po dniach)\n'
    f'{TRAIN_START} → {df["day"].max()} | train={len(train_df)} / test={len(test_df)} dni',
)
plt.xticks(rotation=12, ha='right')
ax.set_ylim(0, float(overall_df['test_mae'].max()) * 1.2)
plt.tight_layout()

bar_path = os.path.join(ROOT, 'reports', 'figures', 'monthly_model_comparison.png')
plt.savefig(bar_path, dpi=150, bbox_inches='tight')
plt.close()
print(f'✅ Wykres (ogólny): {bar_path}')

# ============================================================================
# 8. Opcjonalnie: breakdown miesięczny tylko na TEŚCIE (diagnostyka)
# ============================================================================
print('\n8. Breakdown miesięczny na teście (diagnostyka, nie decyzja)...')
monthly_results = []
for month_name in sorted(test_df['month_name'].unique()):
    month_data = test_df[test_df['month_name'] == month_name]
    for model_name, pred_col in models.items():
        monthly_results.append({
            'month': month_name,
            'model': model_name,
            'mae': mean_absolute_error(month_data[target], month_data[pred_col]),
            'days': len(month_data),
        })
monthly_df = pd.DataFrame(monthly_results)
csv_path = os.path.join(ROOT, 'notebooks', 'monthly_model_comparison.csv')
monthly_df.to_csv(csv_path, index=False)
print(f'✅ CSV (miesięczny, tylko test): {csv_path}')

print('\n' + '=' * 80)
print('GOTOWE — decyzja po Test MAE całego zbioru (pkt 5–6), nie po miesiącach.')
print('=' * 80)
