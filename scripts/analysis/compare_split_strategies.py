"""
Porównanie strategii train/test split z day_length_hours.

Strategia 1: 3 miesiące test (Gru, Lut, Cze) - 10 miesięcy train
Strategia 2: 2 miesiące test (Sty, Cze) - 11 miesięcy train
+ GroupKFold CV dla porównania
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GroupKFold, cross_val_score
from src.features.pv_features import load_training_frame

print('='*80)
print('PORÓWNANIE STRATEGII TRAIN/TEST SPLIT')
print('='*80)

# Load data
df = load_training_frame('data/energy_model.db', '2025-06-01', '2026-06-30', 'home')
df['month'] = pd.to_datetime(df['day']).dt.month
df['year_month'] = pd.to_datetime(df['day']).dt.to_period('M').astype(str)

print(f'\nDane: {len(df)} dni (2025-06 → 2026-06)')
print(f'Dostępne miesiące: {sorted(df["year_month"].unique())}')

# Feature columns
feature_cols = [
    'radiation_daytime_kwh_m2', 'cloud_cover_avg', 'cloud_cover_low_avg',
    'temp_avg', 'temp_min', 'temp_max', 'humidity_daytime_avg',
    'precip_mm', 'om_snowfall_cm', 'om_snow_depth_cm', 'imgw_snow_depth_cm',
    'snow_on_panels', 'snow_on_panels_prev',
    'likely_fog_day', 'rainy_day', 'day_length_hours',
    'doy_sin', 'doy_cos', 'month'
]

# Check if day_length_hours exists
if 'day_length_hours' not in df.columns:
    print('\n⚠️  UWAGA: day_length_hours nie istnieje w danych!')
    feature_cols.remove('day_length_hours')
else:
    print(f'\n✅ day_length_hours dostępne: {df["day_length_hours"].min():.1f} - {df["day_length_hours"].max():.1f}h')

target = 'pv_kwh'

# Baseline for comparison
# Yield z mediany PV/radiacja (stała 0.17 była błędną skalą — zawyżała „poprawę”)
_rad = df['radiation_daytime_kwh_m2'].clip(lower=0.05)
_yield = float((df[target] / _rad).median())
baseline_pred = df['radiation_daytime_kwh_m2'] * _yield
baseline_mae = np.abs(df[target] - baseline_pred).mean()

print(f'\n📊 Baseline (radiacja × yield_med={_yield:.3f}): MAE = {baseline_mae:.3f} kWh')

# ============================================================================
# STRATEGIA 1: 3 miesiące test (Gru, Lut, Cze)
# ============================================================================
print('\n' + '='*80)
print('STRATEGIA 1: Test = Grudzień 2025, Luty 2026, Czerwiec 2026')
print('='*80)

test_months_s1 = ['2025-12', '2026-02', '2026-06']
train_s1 = df[~df['year_month'].isin(test_months_s1)].copy()
test_s1 = df[df['year_month'].isin(test_months_s1)].copy()

print(f'\nTrain: {len(train_s1)} dni ({train_s1["year_month"].nunique()} miesięcy)')
print(f'  Miesiące: {sorted(train_s1["year_month"].unique())}')
print(f'Test:  {len(test_s1)} dni ({test_s1["year_month"].nunique()} miesiące)')
print(f'  Miesiące: {sorted(test_s1["year_month"].unique())}')

X_train_s1 = train_s1[feature_cols].fillna(0)
y_train_s1 = train_s1[target]
X_test_s1 = test_s1[feature_cols].fillna(0)
y_test_s1 = test_s1[target]

rf_s1 = RandomForestRegressor(n_estimators=200, max_depth=12, random_state=42, n_jobs=-1)
rf_s1.fit(X_train_s1, y_train_s1)

train_pred_s1 = rf_s1.predict(X_train_s1)
test_pred_s1 = rf_s1.predict(X_test_s1)

train_mae_s1 = np.abs(y_train_s1 - train_pred_s1).mean()
test_mae_s1 = np.abs(y_test_s1 - test_pred_s1).mean()
test_r2_s1 = 1 - (np.sum((y_test_s1 - test_pred_s1)**2) / np.sum((y_test_s1 - y_test_s1.mean())**2))

print(f'\nTrain MAE: {train_mae_s1:.3f} kWh')
print(f'Test MAE:  {test_mae_s1:.3f} kWh')
print(f'Test R²:   {test_r2_s1:.3f}')
print(f'Gap:       {test_mae_s1 - train_mae_s1:.3f} kWh')

# Per-month breakdown
print(f'\nWyniki per miesiąc testowy:')
for month in test_months_s1:
    month_data = test_s1[test_s1['year_month'] == month]
    month_pred = test_pred_s1[test_s1['year_month'] == month]
    month_mae = np.abs(month_data[target] - month_pred).mean()
    print(f'  {month}: MAE = {month_mae:.3f} kWh ({len(month_data)} dni)')

# ============================================================================
# STRATEGIA 2: 2 miesiące test (Sty, Cze)
# ============================================================================
print('\n' + '='*80)
print('STRATEGIA 2: Test = Styczeń 2026, Czerwiec 2026')
print('='*80)

test_months_s2 = ['2026-01', '2026-06']
train_s2 = df[~df['year_month'].isin(test_months_s2)].copy()
test_s2 = df[df['year_month'].isin(test_months_s2)].copy()

print(f'\nTrain: {len(train_s2)} dni ({train_s2["year_month"].nunique()} miesięcy)')
print(f'  Miesiące: {sorted(train_s2["year_month"].unique())}')
print(f'Test:  {len(test_s2)} dni ({test_s2["year_month"].nunique()} miesiące)')
print(f'  Miesiące: {sorted(test_s2["year_month"].unique())}')

X_train_s2 = train_s2[feature_cols].fillna(0)
y_train_s2 = train_s2[target]
X_test_s2 = test_s2[feature_cols].fillna(0)
y_test_s2 = test_s2[target]

rf_s2 = RandomForestRegressor(n_estimators=200, max_depth=12, random_state=42, n_jobs=-1)
rf_s2.fit(X_train_s2, y_train_s2)

train_pred_s2 = rf_s2.predict(X_train_s2)
test_pred_s2 = rf_s2.predict(X_test_s2)

train_mae_s2 = np.abs(y_train_s2 - train_pred_s2).mean()
test_mae_s2 = np.abs(y_test_s2 - test_pred_s2).mean()
test_r2_s2 = 1 - (np.sum((y_test_s2 - test_pred_s2)**2) / np.sum((y_test_s2 - y_test_s2.mean())**2))

print(f'\nTrain MAE: {train_mae_s2:.3f} kWh')
print(f'Test MAE:  {test_mae_s2:.3f} kWh')
print(f'Test R²:   {test_r2_s2:.3f}')
print(f'Gap:       {test_mae_s2 - train_mae_s2:.3f} kWh')

# Per-month breakdown
print(f'\nWyniki per miesiąc testowy:')
for month in test_months_s2:
    month_data = test_s2[test_s2['year_month'] == month]
    month_pred = test_pred_s2[test_s2['year_month'] == month]
    month_mae = np.abs(month_data[target] - month_pred).mean()
    print(f'  {month}: MAE = {month_mae:.3f} kWh ({len(month_data)} dni)')

# ============================================================================
# GROUPKFOLD CV=5 (Automatyczny 80/20)
# ============================================================================
print('\n' + '='*80)
print('GROUPKFOLD CV=5: Automatyczny rotacyjny 80/20')
print('='*80)

X_all = df[feature_cols].fillna(0)
y_all = df[target]
groups = pd.to_datetime(df['day']).dt.to_period('M').astype(str)

cv = GroupKFold(n_splits=5)
rf_cv = RandomForestRegressor(n_estimators=200, max_depth=12, random_state=42, n_jobs=-1)

scores = cross_val_score(rf_cv, X_all, y_all, groups=groups, cv=cv, 
                         scoring='neg_mean_absolute_error', n_jobs=-1)
mae_scores = -scores

print(f'\nWyniki 5 foldów:')
for i, score in enumerate(mae_scores, 1):
    print(f'  Fold {i}: MAE = {score:.3f} kWh')

print(f'\nCV średnie: {mae_scores.mean():.3f} ± {mae_scores.std():.3f} kWh')

# ============================================================================
# PORÓWNANIE
# ============================================================================
print('\n' + '='*80)
print('PORÓWNANIE WSZYSTKICH STRATEGII')
print('='*80)

results = pd.DataFrame({
    'Strategia': [
        'Baseline (radiacja×yield)',
        'Strategia 1 (test: Gru,Lut,Cze)',
        'Strategia 2 (test: Sty,Cze)',
        'GroupKFold CV=5',
    ],
    'Train dni': [
        '-',
        len(train_s1),
        len(train_s2),
        f'~{len(df)*0.8:.0f}',
    ],
    'Test dni': [
        '-',
        len(test_s1),
        len(test_s2),
        f'~{len(df)*0.2:.0f}',
    ],
    'MAE (kWh)': [
        baseline_mae,
        test_mae_s1,
        test_mae_s2,
        mae_scores.mean(),
    ],
    'R²': [
        '-',
        f'{test_r2_s1:.3f}',
        f'{test_r2_s2:.3f}',
        '-',
    ],
    'Poprawa vs baseline': [
        '-',
        f'{(1 - test_mae_s1/baseline_mae)*100:.1f}%',
        f'{(1 - test_mae_s2/baseline_mae)*100:.1f}%',
        f'{(1 - mae_scores.mean()/baseline_mae)*100:.1f}%',
    ]
})

print('\n' + results.to_string(index=False))

# Feature importance dla najlepszej strategii
best_strategy = 's1' if test_mae_s1 < test_mae_s2 else 's2'
rf_best = rf_s1 if best_strategy == 's1' else rf_s2

print(f'\n📊 Top 10 cech ({"Strategia 1" if best_strategy == "s1" else "Strategia 2"}):')
importances = pd.DataFrame({
    'feature': feature_cols,
    'importance': rf_best.feature_importances_
}).sort_values('importance', ascending=False)

for idx, row in importances.head(10).iterrows():
    print(f'  {row["feature"]:30s} {row["importance"]:.6f}')

# Check day_length importance
if 'day_length_hours' in feature_cols:
    day_length_imp = importances[importances['feature'] == 'day_length_hours']['importance'].values
    if len(day_length_imp) > 0:
        rank = importances[importances['feature'] == 'day_length_hours'].index[0] + 1
        print(f'\n📏 day_length_hours: importance={day_length_imp[0]:.6f}, rank={rank}/{len(feature_cols)}')

print('\n' + '='*80)
print('WNIOSKI')
print('='*80)

best_name = 'Strategia 1' if test_mae_s1 < test_mae_s2 else 'Strategia 2'
best_mae = min(test_mae_s1, test_mae_s2)
cv_mae = mae_scores.mean()

print(f'\n✅ Najlepsza strategia: {best_name}')
print(f'   MAE = {best_mae:.3f} kWh')
print(f'\n📊 GroupKFold CV=5: MAE = {cv_mae:.3f} ± {mae_scores.std():.3f} kWh')
print(f'   Różnica vs najlepsze: {abs(cv_mae - best_mae):.3f} kWh')

if abs(cv_mae - best_mae) < 0.1:
    print('\n💡 CV i najlepsza strategia dają podobne wyniki - model stabilny!')
elif cv_mae < best_mae:
    print('\n⚠️  CV daje lepsze wyniki - może warto użyć całego datasetu?')
else:
    print(f'\n⚠️  CV gorsze od fixed split - możliwy overfitting w CV')

print('\n✅ Skrypt zakończony')
