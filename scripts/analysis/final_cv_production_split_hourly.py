"""
FINALNA STRATEGIA: 12-miesięcy Development + Production Holdout
MODEL GODZINOWY

Development Set (CV): 2025-06 → 2026-05 (12 miesięcy, pełny cykl)
  - GroupKFold(n_splits=5) po miesiącach
  - Automatyczny 80/20 w każdym foldzie
  - Dobór hiperparametrów, feature importance

Production Holdout: 2026-06 → 2026-07 (dane przyszłe)
  - Finalna walidacja na nieznanym okresie
  - Symulacja rzeczywistego użycia
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GroupKFold, cross_val_score, cross_validate
from src.features.pv_features_hourly_extended import load_hourly_training_frame_extended
from src.data.household_context import (
    DEVELOPMENT_END,
    PRODUCTION_HOLDOUT_END,
    PRODUCTION_HOLDOUT_START,
    development_date_range,
)

RAD_COL = 'radiation_wm2'


def _fit_radiation_yield(rad, y, min_rad: float = 1.0) -> tuple[float, float]:
    """Dopasuj coef = PV_hour / radiation_wm2 na train: mediana oraz OLS."""
    rad = np.asarray(rad, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(rad) & np.isfinite(y) & (rad > min_rad)
    rad_m, y_m = rad[mask], y[mask]
    if len(rad_m) == 0:
        return float('nan'), float('nan')
    yield_med = float(np.median(y_m / rad_m))
    yield_ols = float(np.dot(rad_m, y_m) / np.dot(rad_m, rad_m))
    return yield_med, yield_ols


print('='*80)
print('FINALNA STRATEGIA: Development (CV) + Production Holdout')
print('MODEL GODZINOWY')
print('='*80)

# Load full data with fog flags
dev_start, _ = development_date_range()
df_full = load_hourly_training_frame_extended(
    'data/energy_model.db',
    dev_start,
    PRODUCTION_HOLDOUT_END.isoformat(),
    'home',
    use_fog_flags=True,
)

# Filter: only daylight hours (sunrise to sunset)
df_full = df_full[
    (df_full['hour'] >= df_full['sunrise_hour']) & 
    (df_full['hour'] <= df_full['sunset_hour'])
].copy()

# Create datetime column from day + hour
df_full['datetime'] = pd.to_datetime(df_full['day']) + pd.to_timedelta(df_full['hour'], unit='h')
df_full['month'] = df_full['datetime'].dt.month
df_full['year_month'] = df_full['datetime'].dt.to_period('M').astype(str)

print(f'\nŁącznie danych: {len(df_full)} godzin (tylko dzienne)')
print(f'Zakres: {df_full["datetime"].min()} → {df_full["datetime"].max()}')

# Split: Development vs Production
dev_df = df_full[df_full['day'] <= DEVELOPMENT_END.isoformat()].copy()
prod_df = df_full[
    (df_full['day'] >= PRODUCTION_HOLDOUT_START.isoformat())
    & (df_full['day'] <= PRODUCTION_HOLDOUT_END.isoformat())
].copy()

print(f'\n📊 DEVELOPMENT SET (CV): {len(dev_df)} godzin')
print(f'  Okres: 2025-06 → 2026-05')
print(f'  Miesiące: {sorted(dev_df["year_month"].unique())}')

# Check seasons in dev
def get_season(month):
    if month in [3, 4, 5]:
        return 'Wiosna'
    elif month in [6, 7, 8]:
        return 'Lato'
    elif month in [9, 10, 11]:
        return 'Jesień'
    else:
        return 'Zima'

dev_df['season'] = dev_df['datetime'].dt.month.apply(get_season)
season_counts = dev_df.groupby('season').size()
print(f'\n  Sezony w development:')
for season in ['Wiosna', 'Lato', 'Jesień', 'Zima']:
    count = season_counts.get(season, 0)
    print(f'    {season}: {count} godzin ({count/len(dev_df)*100:.1f}%)')

print(f'\n🎯 PRODUCTION HOLDOUT: {len(prod_df)} godzin')
print(f'  Okres: {PRODUCTION_HOLDOUT_START} → {PRODUCTION_HOLDOUT_END}')
print(f'  Miesiące: {sorted(prod_df["year_month"].unique())}')
print(f'  Cel: Finalna walidacja na przyszłych danych')

# Feature columns (hourly extended) - USE ONLY COLUMNS THAT EXIST!
feature_cols = [
    'radiation_wm2',  # Promieniowanie słoneczne
    'cloud_cover_pct',  # Zachmurzenie
    'temp_c',  # Temperatura
    'humidity_pct',  # Wilgotność
    'wind_speed_ms',  # Wiatr
    'snow_on_panels',  # Flaga śniegu (dzienne)
    'snow_on_panels_prev',  # Flaga śniegu (poprzedni dzień)
    'likely_fog_day',  # Flaga mgły (dzienne)
    'day_length_hours',  # Długość dnia
    'hours_since_sunrise',  # Czas od wschodu
    'hours_until_sunset',  # Czas do zachodu
    'sun_position',  # Pozycja słońca (0-1)
    'doy_sin', 'doy_cos',  # Dzień roku (cykliczny)
    'month',  # Miesiąc
    'hour',  # Godzina
]

# Verify day_length_hours
if 'day_length_hours' not in dev_df.columns:
    print('\n⚠️  day_length_hours brak!')
    feature_cols.remove('day_length_hours')
else:
    print(f'\n✅ day_length_hours: {dev_df["day_length_hours"].min():.1f} - {dev_df["day_length_hours"].max():.1f}h')

target = 'pv_kwh_hour'

# ============================================================================
# PHASE 1: GroupKFold Cross-Validation (Development)
# ============================================================================
print('\n' + '='*80)
print('PHASE 1: GroupKFold CV=5 (Development Set)')
print('='*80)

X_dev = dev_df[feature_cols].fillna(0)
y_dev = dev_df[target]
groups_dev = dev_df['year_month']  # Already created from datetime

print(f'\nDane: {len(X_dev)} próbek, {len(feature_cols)} cech')
print(f'Grupy (miesiące): {groups_dev.nunique()} unikalnych')

cv = GroupKFold(n_splits=5)
rf_cv = RandomForestRegressor(n_estimators=200, max_depth=15, min_samples_split=10, random_state=42, n_jobs=1)

# Baseline rad×coef: coef tylko z fold-train (OOF), nie ze stałej 0.0024
print('\n📊 Baseline (rad×coef) — coef z train każdego folda:')
baseline_fold_mae_med = []
baseline_fold_mae_ols = []
fold_yields_med = []
fold_yields_ols = []
for fold_i, (train_idx, test_idx) in enumerate(cv.split(X_dev, y_dev, groups=groups_dev), start=1):
    y_med, y_ols = _fit_radiation_yield(
        dev_df.iloc[train_idx][RAD_COL], y_dev.iloc[train_idx],
    )
    rad_te = dev_df.iloc[test_idx][RAD_COL].to_numpy(dtype=float)
    y_te = y_dev.iloc[test_idx].to_numpy(dtype=float)
    mae_med = float(np.abs(y_te - rad_te * y_med).mean())
    mae_ols = float(np.abs(y_te - rad_te * y_ols).mean())
    baseline_fold_mae_med.append(mae_med)
    baseline_fold_mae_ols.append(mae_ols)
    fold_yields_med.append(y_med)
    fold_yields_ols.append(y_ols)
    print(
        f'  Fold {fold_i}: coef_med={y_med:.5f}, coef_ols={y_ols:.5f} | '
        f'MAE_med={mae_med:.3f}, MAE_ols={mae_ols:.3f}'
    )

baseline_mae = float(np.mean(baseline_fold_mae_med))
baseline_mae_ols = float(np.mean(baseline_fold_mae_ols))
print(
    f'\n  CV baseline MAE (median coef): {baseline_mae:.3f} ± '
    f'{np.std(baseline_fold_mae_med):.3f} kWh'
)
print(
    f'  CV baseline MAE (OLS coef):    {baseline_mae_ols:.3f} ± '
    f'{np.std(baseline_fold_mae_ols):.3f} kWh'
)
print(
    f'  Coef (średnia foldów): med={np.mean(fold_yields_med):.5f}, '
    f'ols={np.mean(fold_yields_ols):.5f}'
)

print(f'\nUruchamianie CV (5 foldów, może potrwać ~2-3 min)...')

# Run CV with detailed scoring
cv_results = cross_validate(
    rf_cv, X_dev, y_dev, 
    groups=groups_dev, 
    cv=cv,
    scoring={'mae': 'neg_mean_absolute_error',
             'r2': 'r2'},
    return_train_score=True,
    n_jobs=1  # Sequential to avoid permission errors
)

train_mae = -cv_results['train_mae']
test_mae = -cv_results['test_mae']
test_r2 = cv_results['test_r2']

print(f'\n📊 Wyniki CV (5 foldów):')
print(f'{"Fold":>6s} {"Train MAE":>12s} {"Test MAE":>12s} {"Test R²":>10s} {"Gap":>10s}')
print('-'*55)
for i in range(5):
    gap = test_mae[i] - train_mae[i]
    print(f'  {i+1:2d}   {train_mae[i]:10.3f}   {test_mae[i]:10.3f}   {test_r2[i]:8.3f}   {gap:8.3f}')

print(f'\n{"Średnia":>6s} {train_mae.mean():10.3f}   {test_mae.mean():10.3f}   {test_r2.mean():8.3f}   {test_mae.mean()-train_mae.mean():8.3f}')
print(f'{"Std":>6s} {train_mae.std():10.3f}   {test_mae.std():10.3f}   {test_r2.std():8.3f}')

print(f'\n✅ CV Summary:')
print(f'  Test MAE: {test_mae.mean():.3f} ± {test_mae.std():.3f} kWh')
print(f'  Test R²:  {test_r2.mean():.3f} ± {test_r2.std():.3f}')
print(f'  Poprawa vs baseline (median coef, OOF): {(1 - test_mae.mean()/baseline_mae)*100:.1f}%')

# ============================================================================
# PHASE 2: Train on Full Development Set
# ============================================================================
print('\n' + '='*80)
print('PHASE 2: Train na pełnym Development Set')
print('='*80)

print(f'\nTrenuję finalny model na wszystkich {len(dev_df)} godzinach...')

rf_final = RandomForestRegressor(n_estimators=200, max_depth=15, min_samples_split=10, random_state=42, n_jobs=-1)
rf_final.fit(X_dev, y_dev)

dev_pred = rf_final.predict(X_dev)
dev_mae = np.abs(y_dev - dev_pred).mean()
dev_r2 = 1 - (np.sum((y_dev - dev_pred)**2) / np.sum((y_dev - y_dev.mean())**2))

print(f'\nDevelopment Set (train):')
print(f'  MAE: {dev_mae:.3f} kWh')
print(f'  R²:  {dev_r2:.3f}')

# Feature Importance
print(f'\n📊 Top 10 Features:')
importances = pd.DataFrame({
    'feature': feature_cols,
    'importance': rf_final.feature_importances_
}).sort_values('importance', ascending=False)

for idx, row in importances.head(10).iterrows():
    print(f'  {row["feature"]:30s} {row["importance"]:.6f}')

if 'day_length_hours' in feature_cols:
    day_length_row = importances[importances['feature'] == 'day_length_hours']
    if len(day_length_row) > 0:
        rank = (importances['importance'] > day_length_row['importance'].values[0]).sum() + 1
        imp = day_length_row['importance'].values[0]
        print(f'\n📏 day_length_hours: importance={imp:.6f}, rank={rank}/{len(feature_cols)}')

# ============================================================================
# PHASE 3: Production Holdout Test
# ============================================================================
print('\n' + '='*80)
print('PHASE 3: Production Holdout Test (Czerwiec-Lipiec 2026)')
print('='*80)

X_prod = prod_df[feature_cols].fillna(0)
y_prod = prod_df[target]

print(f'\nPredykcja na {len(prod_df)} godzinach przyszłości...')

prod_pred = rf_final.predict(X_prod)
prod_mae = np.abs(y_prod - prod_pred).mean()
prod_r2 = 1 - (np.sum((y_prod - prod_pred)**2) / np.sum((y_prod - y_prod.mean())**2))

print(f'\n🎯 PRODUCTION HOLDOUT RESULTS:')
print(f'  MAE:  {prod_mae:.3f} kWh')
print(f'  R²:   {prod_r2:.3f}')
print(f'  RMSE: {np.sqrt(np.mean((y_prod - prod_pred)**2)):.3f} kWh')

# Baseline na holdoucie: coef wyłącznie z development (train), ocena na production
yield_dev_med, yield_dev_ols = _fit_radiation_yield(dev_df[RAD_COL], y_dev)
prod_rad = prod_df[RAD_COL].to_numpy(dtype=float)
baseline_prod_mae = float(np.abs(y_prod.to_numpy(dtype=float) - prod_rad * yield_dev_med).mean())
baseline_prod_mae_ols = float(np.abs(y_prod.to_numpy(dtype=float) - prod_rad * yield_dev_ols).mean())
print(
    f'\n📊 Baseline na Production (coef z Development): '
    f'med={yield_dev_med:.5f} → MAE={baseline_prod_mae:.3f}; '
    f'ols={yield_dev_ols:.5f} → MAE={baseline_prod_mae_ols:.3f}'
)
print(f'  Poprawa RF vs baseline (median): {(1 - prod_mae / baseline_prod_mae) * 100:.1f}%')

# Per month
prod_df['pred'] = prod_pred
for month in sorted(prod_df['year_month'].unique()):
    month_data = prod_df[prod_df['year_month'] == month]
    month_mae = np.abs(month_data[target] - month_data['pred']).mean()
    print(f'\n  {month}: MAE = {month_mae:.3f} kWh ({len(month_data)} godzin)')

# ============================================================================
# FINAL COMPARISON
# ============================================================================
print('\n' + '='*80)
print('PODSUMOWANIE KOŃCOWE')
print('='*80)

results = pd.DataFrame({
    'Zbiór': [
        'Baseline CV (rad×coef_med, OOF)',
        'CV Mean (5-fold)',
        'Development (full train)',
        'Baseline Prod (coef z Dev)',
        'Production Holdout ⭐',
    ],
    'Liczba próbek': [
        f'~{len(dev_df)*0.2:.0f} (per fold)',
        f'~{len(dev_df)*0.2:.0f} (per fold)',
        len(dev_df),
        len(prod_df),
        len(prod_df),
    ],
    'MAE (kWh)': [
        f'{baseline_mae:.3f} ± {np.std(baseline_fold_mae_med):.3f}',
        f'{test_mae.mean():.3f} ± {test_mae.std():.3f}',
        f'{dev_mae:.3f}',
        f'{baseline_prod_mae:.3f}',
        f'{prod_mae:.3f}',
    ],
    'R²': [
        '-',
        f'{test_r2.mean():.3f}',
        f'{dev_r2:.3f}',
        '-',
        f'{prod_r2:.3f}',
    ],
    'Poprawa': [
        '-',
        f'{(1-test_mae.mean()/baseline_mae)*100:.1f}%',
        '-',
        '-',
        f'{(1-prod_mae/baseline_prod_mae)*100:.1f}%',
    ]
})

print('\n' + results.to_string(index=False))

# ============================================================================
# WNIOSKI
# ============================================================================
print('\n' + '='*80)
print('WNIOSKI')
print('='*80)

print(f'\n✅ CV VALIDATION:')
print(f'   - 5 foldów z różnymi miesiącami')
print(f'   - Średnie MAE: {test_mae.mean():.3f} kWh')
print(f'   - Stabilność: ±{test_mae.std():.3f} kWh')

print(f'\n🎯 PRODUCTION HOLDOUT:')
print(f'   - Test na przyszłych danych (cze-lip 2026)')
print(f'   - MAE: {prod_mae:.3f} kWh')
print(f'   - R²: {prod_r2:.3f}')

diff_cv_prod = abs(test_mae.mean() - prod_mae)
if diff_cv_prod < 0.1:
    print(f'\n💡 CV i Production są zgodne (Δ={diff_cv_prod:.3f} kWh)')
    print(f'   → Model generalizuje dobrze! ✅')
elif prod_mae < test_mae.mean():
    print(f'\n💡 Production lepsze niż CV (Δ={diff_cv_prod:.3f} kWh)')
    print(f'   → Czerwiec-lipiec łatwiejsze do predykcji')
else:
    print(f'\n⚠️  Production gorsze niż CV (Δ={diff_cv_prod:.3f} kWh)')
    print(f'   → Czerwiec-lipiec trudniejsze (może: nowe wzorce?)')

print(f'\n📏 day_length_hours:')
if 'day_length_hours' in feature_cols:
    print(f'   ✅ Dodana i działa')
else:
    print(f'   ❌ Nie dodana')

print('\n' + '='*80)
print('✅ Analiza zakończona!')
print('='*80)
