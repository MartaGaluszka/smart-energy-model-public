"""
Porównanie modeli PV — dokładność miesięczna

Modele do porównania:
1. RF + cechy kalibracyjne (śnieg, mgła, deszcz) — pełny feature engineering
2. RF bez cech kalibracyjnych (baseline)
3. Regresja liniowa (Ridge)
4. XGBoost
5. Model godzinowy produkcyjny (GridSearch, agregacja do dnia)
"""

from datetime import date

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from src.data.household_context import (
    DEVELOPMENT_END,
    PRODUCTION_HOLDOUT_END,
    PRODUCTION_HOLDOUT_START,
    development_date_range,
)
from src.features.pv_features import TARGET_COLUMN, load_training_frame
from src.features.pv_features_hourly_extended import load_hourly_training_frame_extended
from src.models.pv_hourly_predictor import (
    RF_MAX_DEPTH,
    RF_MAX_FEATURES,
    RF_MIN_SAMPLES_LEAF,
    RF_MIN_SAMPLES_SPLIT,
    RF_N_ESTIMATORS,
    RF_RANDOM_STATE,
)

DEV_START, _ = development_date_range()
DATA_END = PRODUCTION_HOLDOUT_END.isoformat()
PROD_START = PRODUCTION_HOLDOUT_START.isoformat()

print('='*80)
print('PORÓWNANIE MODELI — DOKŁADNOŚĆ MIESIĘCZNA')
print('='*80)

# ============================================================================
# 1. Wczytaj dane dzienne
# ============================================================================
print('\n1. Wczytanie danych dziennych...')
df = load_training_frame('data/energy_model.db', DEV_START, DATA_END, 'home')
df['month_name'] = pd.to_datetime(df['day']).dt.strftime('%Y-%m')
df['month_num'] = pd.to_datetime(df['day']).dt.month

# Split: Development vs Production (tak jak w finalnej strategii)
dev_df = df[df['day'] <= DEVELOPMENT_END.isoformat()].copy()
prod_df = df[
    (df['day'] >= PROD_START) & (df['day'] <= DATA_END)
].copy()

print(f'  Development: {len(dev_df)} dni ({DEV_START} → {DEVELOPMENT_END})')
print(f'  Production: {len(prod_df)} dni ({PROD_START} → {DATA_END})')

# ============================================================================
# 2. Przygotuj feature sets
# ============================================================================
print('\n2. Przygotowanie zestawów cech...')

# Pełny zestaw (cechy kalibracyjne: śnieg, mgła, deszcz)
full_features = [
    'radiation_daytime_kwh_m2', 'cloud_cover_avg', 'cloud_cover_low_avg',
    'temp_avg', 'temp_min', 'temp_max', 'humidity_daytime_avg',
    'precip_mm', 'om_snowfall_cm', 'om_snow_depth_cm', 'imgw_snow_depth_cm',
    'snow_on_panels', 'snow_on_panels_prev',
    'likely_fog_day', 'rainy_day',
    'day_length_hours',
    'doy_sin', 'doy_cos', 'month'
]

# Baseline (bez cech kalibracyjnych)
baseline_features = [
    'radiation_daytime_kwh_m2', 'cloud_cover_avg', 'cloud_cover_low_avg',
    'temp_avg', 'temp_min', 'temp_max', 'humidity_daytime_avg',
    'precip_mm', 'om_snowfall_cm', 'om_snow_depth_cm', 'imgw_snow_depth_cm',
    # BEZ: snow_on_panels, likely_fog_day, rainy_day
    'day_length_hours',
    'doy_sin', 'doy_cos', 'month'
]

target = TARGET_COLUMN

print(f'  Pełny zestaw: {len(full_features)} cech (z kalibracją pogodową)')
print(f'  Baseline: {len(baseline_features)} cech (bez kalibracji)')

# ============================================================================
# 3. Trenuj modele na pełnym development set
# ============================================================================
print('\n3. Trening modeli...')

X_full_dev = dev_df[full_features].fillna(0)
X_baseline_dev = dev_df[baseline_features].fillna(0)
y_dev = dev_df[target]

X_full_prod = prod_df[full_features].fillna(0)
X_baseline_prod = prod_df[baseline_features].fillna(0)
y_prod = prod_df[target]

# Model 1: RF + cechy kalibracyjne
print('  [1/4] RF + cechy kalibracyjne...')
rf_full = RandomForestRegressor(n_estimators=200, max_depth=12, random_state=42, n_jobs=-1)
rf_full.fit(X_full_dev, y_dev)

# Model 2: RF baseline
print('  [2/4] RF bez cech kalibracyjnych...')
rf_baseline = RandomForestRegressor(n_estimators=200, max_depth=12, random_state=42, n_jobs=-1)
rf_baseline.fit(X_baseline_dev, y_dev)

# Model 3: Ridge (regresja liniowa)
print('  [3/4] Ridge (regresja liniowa)...')
scaler_full = StandardScaler()
X_full_dev_scaled = scaler_full.fit_transform(X_full_dev)
X_full_prod_scaled = scaler_full.transform(X_full_prod)

# Use higher alpha to prevent numerical issues
ridge = Ridge(alpha=10.0, random_state=42)
ridge.fit(X_full_dev_scaled, y_dev)

# Model 4: XGBoost
print('  [4/4] XGBoost...')
xgb = XGBRegressor(n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1)
xgb.fit(X_full_dev, y_dev)

# ============================================================================
# 4. Wczytaj dane godzinowe i agreguj do dnia
# ============================================================================
print('\n4. Wczytanie danych godzinowych...')
df_hourly = load_hourly_training_frame_extended(
    'data/energy_model.db',
    DEV_START,
    DATA_END,
    'home',
    use_fog_flags=True,
)

# Filter: only daylight hours
df_hourly = df_hourly[
    (df_hourly['hour'] >= df_hourly['sunrise_hour']) & 
    (df_hourly['hour'] <= df_hourly['sunset_hour'])
].copy()

print(f'  Wczytano {len(df_hourly)} godzin produkcji')

# Split
dev_hourly = df_hourly[df_hourly['day'] <= DEVELOPMENT_END.isoformat()].copy()
prod_hourly = df_hourly[
    (df_hourly['day'] >= PROD_START) & (df_hourly['day'] <= DATA_END)
].copy()

# Train model
hourly_features = [
    'radiation_wm2', 'cloud_cover_pct', 'temp_c', 'humidity_pct', 'wind_speed_ms',
    'snow_on_panels', 'snow_on_panels_prev', 'likely_fog_day',
    'day_length_hours', 'hours_since_sunrise', 'hours_until_sunset', 'sun_position',
    'doy_sin', 'doy_cos', 'month', 'hour'
]
hourly_target = 'pv_kwh_hour'

X_hourly_dev = dev_hourly[hourly_features].fillna(0)
y_hourly_dev = dev_hourly[hourly_target]

print('  Trening modelu godzinowego...')
rf_hourly = RandomForestRegressor(
    n_estimators=RF_N_ESTIMATORS,
    max_depth=RF_MAX_DEPTH,
    min_samples_leaf=RF_MIN_SAMPLES_LEAF,
    min_samples_split=RF_MIN_SAMPLES_SPLIT,
    max_features=RF_MAX_FEATURES,
    random_state=RF_RANDOM_STATE,
    n_jobs=-1,
)
rf_hourly.fit(X_hourly_dev, y_hourly_dev)

# Predict hourly
dev_hourly['pred'] = rf_hourly.predict(X_hourly_dev)
prod_hourly['pred'] = rf_hourly.predict(prod_hourly[hourly_features].fillna(0))

# Aggregate to daily
dev_hourly_daily = dev_hourly.groupby('day').agg({
    hourly_target: 'sum',
    'pred': 'sum'
}).reset_index()
dev_hourly_daily.columns = ['day', 'actual', 'pred_hourly']

prod_hourly_daily = prod_hourly.groupby('day').agg({
    hourly_target: 'sum',
    'pred': 'sum'
}).reset_index()
prod_hourly_daily.columns = ['day', 'actual', 'pred_hourly']

print(f'  Zagregowano do {len(dev_hourly_daily)} dni (dev) + {len(prod_hourly_daily)} dni (prod)')

# ============================================================================
# 5. Oblicz predykcje dla wszystkich modeli
# ============================================================================
print('\n5. Obliczanie predykcji...')

# Development predictions
dev_df['pred_rf_full'] = rf_full.predict(X_full_dev)
dev_df['pred_rf_baseline'] = rf_baseline.predict(X_baseline_dev)
dev_df['pred_ridge'] = ridge.predict(X_full_dev_scaled)
dev_df['pred_xgb'] = xgb.predict(X_full_dev)

# Production predictions
prod_df['pred_rf_full'] = rf_full.predict(X_full_prod)
prod_df['pred_rf_baseline'] = rf_baseline.predict(X_baseline_prod)
prod_df['pred_ridge'] = ridge.predict(X_full_prod_scaled)
prod_df['pred_xgb'] = xgb.predict(X_full_prod)

# Merge hourly predictions
dev_df = dev_df.merge(dev_hourly_daily[['day', 'pred_hourly']], on='day', how='left')
prod_df = prod_df.merge(prod_hourly_daily[['day', 'pred_hourly']], on='day', how='left')

# Combine dev + prod
all_df = pd.concat([dev_df, prod_df], ignore_index=True)

# ============================================================================
# 6. Oblicz MAE miesięcznie
# ============================================================================
print('\n6. Obliczanie MAE miesięcznie...')

models = {
    'RF + kalibracja\n(śnieg, mgła, deszcz)': 'pred_rf_full',
    'RF bez kalibracji\n(baseline)': 'pred_rf_baseline',
    'Regresja liniowa\n(Ridge)': 'pred_ridge',
    'XGBoost': 'pred_xgb',
    'RF godzinowy prod.\n(agregacja/dzień)': 'pred_hourly',
}

monthly_results = []

for month_name in sorted(all_df['month_name'].unique()):
    month_data = all_df[all_df['month_name'] == month_name].copy()
    
    for model_name, pred_col in models.items():
        if pred_col in month_data.columns and month_data[pred_col].notna().sum() > 0:
            mae = np.abs(month_data[target] - month_data[pred_col]).mean()
            monthly_results.append({
                'month': month_name,
                'model': model_name,
                'mae': mae,
                'days': len(month_data)
            })

monthly_df = pd.DataFrame(monthly_results)

# ============================================================================
# 7. Oblicz ogólne statystyki
# ============================================================================
print('\n7. Statystyki ogólne (Development Set):')
print(f'{"Model":50s} {"MAE (kWh)":>12s} {"R²":>8s}')
print('-'*72)

for model_name, pred_col in models.items():
    mae = np.abs(dev_df[target] - dev_df[pred_col]).mean()
    r2 = 1 - (np.sum((dev_df[target] - dev_df[pred_col])**2) / 
              np.sum((dev_df[target] - dev_df[target].mean())**2))
    print(f'{model_name:50s} {mae:10.3f}   {r2:8.3f}')

print('\n8. Statystyki ogólne (Production Holdout):')
print(f'{"Model":50s} {"MAE (kWh)":>12s} {"R²":>8s}')
print('-'*72)

for model_name, pred_col in models.items():
    if pred_col in prod_df.columns and prod_df[pred_col].notna().sum() > 0:
        mae = np.abs(prod_df[target] - prod_df[pred_col]).mean()
        r2 = 1 - (np.sum((prod_df[target] - prod_df[pred_col])**2) / 
                  np.sum((prod_df[target] - prod_df[target].mean())**2))
        print(f'{model_name:50s} {mae:10.3f}   {r2:8.3f}')

# ============================================================================
# 8. Stwórz wykres
# ============================================================================
print('\n9. Tworzenie wykresu...')

# Set style
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (16, 9)
plt.rcParams['font.size'] = 10

# Create figure
fig, ax = plt.subplots()

# Define colors
colors = {
    'RF + kalibracja\n(śnieg, mgła, deszcz)': '#2ecc71',
    'RF bez kalibracji\n(baseline)': '#e74c3c',
    'Regresja liniowa\n(Ridge)': '#9b59b6',
    'XGBoost': '#f39c12',
    'RF godzinowy prod.\n(agregacja/dzień)': '#3498db',
}

# Plot lines
for model_name in models.keys():
    model_data = monthly_df[monthly_df['model'] == model_name].sort_values('month')
    ax.plot(model_data['month'], model_data['mae'], 
            marker='o', linewidth=2, markersize=8,
            label=model_name, color=colors[model_name])

# Formatting
ax.set_xlabel('Miesiąc', fontsize=12, fontweight='bold')
ax.set_ylabel('MAE (kWh/dobę)', fontsize=12, fontweight='bold')
ax.set_title(
    f'Porównanie modeli PV — Dokładność miesięczna\n'
    f'(Development: {DEV_START} → {DEVELOPMENT_END}, Production: {PROD_START} → {DATA_END})',
    fontsize=14, fontweight='bold', pad=20,
)

# Rotate x labels
plt.xticks(rotation=45, ha='right')

# Legend
ax.legend(loc='upper left', fontsize=10, frameon=True, shadow=True)

# Grid
ax.grid(True, alpha=0.3, linestyle='--')

# Add vertical line for production holdout
prod_start = '2026-06'
if prod_start in monthly_df['month'].values:
    ax.axvline(x=prod_start, color='red', linestyle='--', linewidth=2, alpha=0.5)
    ax.text(prod_start, ax.get_ylim()[1] * 0.95, ' Production Holdout →', 
            color='red', fontweight='bold', fontsize=10, va='top')

# Tight layout
plt.tight_layout()

# Save
output_path = 'reports/figures/monthly_model_comparison.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight')
print(f'\n✅ Wykres zapisany: {output_path}')

# Don't show in terminal (causes issues)
# plt.show()
plt.close()

# ============================================================================
# 9. Zapisz szczegółowe wyniki do CSV
# ============================================================================
print('\n10. Zapisywanie wyników do CSV...')

csv_path = 'notebooks/monthly_model_comparison.csv'
monthly_df.to_csv(csv_path, index=False)
print(f'✅ Dane zapisane: {csv_path}')

print('\n' + '='*80)
print('GOTOWE!')
print('='*80)
