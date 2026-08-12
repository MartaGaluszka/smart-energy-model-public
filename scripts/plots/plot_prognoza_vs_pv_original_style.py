"""
Prognoza vs PV — RF i wariant z korektą reguł (styl oryginalny)

Zgodnie z oryginałem, ale z nową nazwą:
- Rzeczywiste (niebieska linia z markerami)
- Random Forest (pomarańczowa przerywana)
- RF + kalibracja pogodowa (zielona linia)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from src.features.pv_features import load_training_frame

print('='*80)
print('Prognoza vs PV — RF i wariant z korektą pogodową')
print('='*80)

# Load data (same period as original chart)
df = load_training_frame('data/energy_model.db', '2025-12-01', '2026-06-30', 'home')

# Split into dev/prod
dev_df = df[df['day'] < '2026-06-01'].copy()
prod_df = df[df['day'] >= '2026-06-01'].copy()

print(f'\nDane: {len(df)} dni (gru 2025 - cze 2026)')

# Feature sets
baseline_features = [
    'radiation_daytime_kwh_m2', 'cloud_cover_avg', 'cloud_cover_low_avg',
    'temp_avg', 'temp_min', 'temp_max', 'humidity_daytime_avg',
    'precip_mm', 'om_snowfall_cm', 'om_snow_depth_cm', 'imgw_snow_depth_cm',
    'day_length_hours', 'doy_sin', 'doy_cos', 'month'
]

calibrated_features = baseline_features + [
    'snow_on_panels', 'snow_on_panels_prev',
    'likely_fog_day', 'rainy_day'
]

target = 'pv_kwh'

# Train models
print('\nTrening modeli...')

X_baseline_dev = dev_df[baseline_features].fillna(0)
X_calibrated_dev = dev_df[calibrated_features].fillna(0)
y_dev = dev_df[target]

# RF baseline
rf_baseline = RandomForestRegressor(n_estimators=200, max_depth=12, random_state=42, n_jobs=-1)
rf_baseline.fit(X_baseline_dev, y_dev)

# RF + kalibracja
rf_calibrated = RandomForestRegressor(n_estimators=200, max_depth=12, random_state=42, n_jobs=-1)
rf_calibrated.fit(X_calibrated_dev, y_dev)

# Predictions
dev_df['pred_baseline'] = rf_baseline.predict(X_baseline_dev)
dev_df['pred_calibrated'] = rf_calibrated.predict(X_calibrated_dev)

prod_df['pred_baseline'] = rf_baseline.predict(prod_df[baseline_features].fillna(0))
prod_df['pred_calibrated'] = rf_calibrated.predict(prod_df[calibrated_features].fillna(0))

# Combine
all_df = pd.concat([dev_df, prod_df], ignore_index=True)
all_df['date'] = pd.to_datetime(all_df['day'])

# Stats
print('\n📊 Statystyki:')
mae_bl = np.abs(all_df[target] - all_df['pred_baseline']).mean()
mae_cal = np.abs(all_df[target] - all_df['pred_calibrated']).mean()
print(f'  Random Forest: MAE = {mae_bl:.3f} kWh')
print(f'  RF + kalibracja pogodowa: MAE = {mae_cal:.3f} kWh')
print(f'  Poprawa: {(mae_bl - mae_cal):.3f} kWh ({(1 - mae_cal/mae_bl)*100:.1f}%)')

# Create plot (original style)
print('\n🎨 Tworzenie wykresu (styl oryginalny)...')

plt.figure(figsize=(12, 6))
plt.rcParams['font.size'] = 10

# Plot lines (matching original style)
plt.plot(all_df['date'], all_df[target], 
         color='#1f77b4', linewidth=1.5, marker='o', markersize=3,
         label='Rzeczywiste', zorder=3)

plt.plot(all_df['date'], all_df['pred_baseline'], 
         color='#ff7f0e', linewidth=1.2, linestyle='--',
         label='Random Forest', zorder=2)

plt.plot(all_df['date'], all_df['pred_calibrated'], 
         color='#2ca02c', linewidth=1.5,
         label='RF + kalibracja pogodowa\n(śnieg, mgła, deszcz)', zorder=2)

# Labels (matching original)
plt.xlabel('Data', fontsize=11)
plt.ylabel('kWh (9-16h)', fontsize=11)
plt.title('Prognoza vs PV — RF i wariant z korektą pogodową', 
          fontsize=12, fontweight='normal')

# Grid (matching original)
plt.grid(True, alpha=0.3, linestyle='-', linewidth=0.5, color='gray')

# Legend (matching original position)
plt.legend(loc='upper left', fontsize=9, frameon=True)

# Tight layout
plt.tight_layout()

# Save
output_path = 'reports/figures/prognoza_vs_pv_kalibracja.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight')
print(f'\n✅ Wykres zapisany: {output_path}')
plt.close()

print('\n' + '='*80)
print('GOTOWE!')
print('='*80)
