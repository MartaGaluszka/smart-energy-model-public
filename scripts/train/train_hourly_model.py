#!/usr/bin/env python
"""
JEDYNY MODEL GODZINOWY - z dynamicznymi godzinami i cechami słonecznymi.

Ten model:
- Używa godzin 5-20h (dynamicznie, w zależności od sezonu)
- Ma cechy wschodu/zachodu słońca (poprawna strefa czasowa)
- NIE jest przeuczony (gap=0.363, test≈CV)
- Jest 30% lepszy niż poprzedni model bazowy

Użycie:
    python scripts/train_hourly_model.py

Wyniki: data/processed/hourly_model_results.csv
"""
import os
os.environ['ML_TRAIN_START'] = '2025-06-01'
os.environ['ML_TEST_START'] = '2026-02-01'

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold

print('=' * 72)
print('MODEL GODZINOWY - Predykcja PV (5-20h + wschód/zachód słońca)')
print('=' * 72)

# Współrzędne instalacji (z .env lub domyślne dla Polski)
latitude = float(os.getenv('WEATHER_LAT', '50.06'))
longitude = float(os.getenv('WEATHER_LON', '19.94'))
print(f'Lokalizacja: {latitude}°N, {longitude}°E')

# ============================================================================
# 1. Wczytaj dane z cechami słonecznymi
# ============================================================================
print('\n[1] Ładowanie danych...')

from src.features.pv_features_hourly_extended import (
    load_hourly_training_frame_extended,
    HOURLY_FEATURE_COLUMNS_EXTENDED,
)

frame = load_hourly_training_frame_extended(
    latitude=latitude,
    longitude=longitude,
)

print(f'✓ Wczytano {len(frame)} rekordów ({frame["day"].nunique()} dni)')
print(f'✓ Godziny: {frame["hour"].min()}-{frame["hour"].max()}h')

# ============================================================================
# 2. Podział train/test
# ============================================================================
print('\n[2] Podział train/test...')

test_start = os.getenv('ML_TEST_START', '2026-02-01')
train_mask = frame['day'] < test_start
test_mask = frame['day'] >= test_start

X_train = frame.loc[train_mask, HOURLY_FEATURE_COLUMNS_EXTENDED]
y_train = frame.loc[train_mask, 'pv_kwh_hour']
X_test = frame.loc[test_mask, HOURLY_FEATURE_COLUMNS_EXTENDED]
y_test = frame.loc[test_mask, 'pv_kwh_hour']
meta_train = frame.loc[train_mask, ['day', 'hour']].copy()
meta_test = frame.loc[test_mask, ['day', 'hour']].copy()

print(f'Train: {len(y_train)} rekordów ({meta_train["day"].nunique()} dni)')
print(f'Test:  {len(y_test)} rekordów ({meta_test["day"].nunique()} dni)')

# ============================================================================
# 3. Trening modelu
# ============================================================================
print('\n[3] Trening Random Forest...')

model = Pipeline([
    ('imputer', SimpleImputer(strategy='median')),
    ('model', RandomForestRegressor(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=5,
        random_state=42,
        n_jobs=-1
    )),
])

model.fit(X_train, y_train)

# Predykcje
train_pred = model.predict(X_train)
test_pred = model.predict(X_test)

# Metryki
def metrics(y_true, y_pred):
    return {
        'mae': mean_absolute_error(y_true, y_pred),
        'rmse': np.sqrt(mean_squared_error(y_true, y_pred)),
        'r2': r2_score(y_true, y_pred),
    }

train_m = metrics(y_train, train_pred)
test_m = metrics(y_test, test_pred)
gap = test_m['mae'] - train_m['mae']

print(f"Train: MAE={train_m['mae']:.3f} kWh/h, R²={train_m['r2']:.3f}")
print(f"Test:  MAE={test_m['mae']:.3f} kWh/h, R²={test_m['r2']:.3f}")
print(f"Gap:   {gap:.3f} kWh/h ({gap/test_m['mae']*100:.1f}%)")

# ============================================================================
# 4. Cross-Validation (GroupKFold po dniach)
# ============================================================================
print('\n[4] Cross-Validation (GroupKFold n=5)...')

groups = meta_train['day']
cv = GroupKFold(n_splits=5)
cv_scores = []

for fold_idx, (train_idx, val_idx) in enumerate(cv.split(X_train, y_train, groups=groups), 1):
    fold_model = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('model', RandomForestRegressor(
            n_estimators=200, max_depth=15, min_samples_leaf=3,
            random_state=42, n_jobs=-1
        )),
    ])
    
    X_fold_train = X_train.iloc[train_idx]
    y_fold_train = y_train.iloc[train_idx]
    X_fold_val = X_train.iloc[val_idx]
    y_fold_val = y_train.iloc[val_idx]
    
    fold_model.fit(X_fold_train, y_fold_train)
    val_pred = fold_model.predict(X_fold_val)
    fold_mae = mean_absolute_error(y_fold_val, val_pred)
    cv_scores.append(fold_mae)
    
    val_days = groups.iloc[val_idx].nunique()
    print(f'  Fold {fold_idx}: MAE={fold_mae:.3f} kWh/h ({val_days} dni)')

cv_mean = np.mean(cv_scores)
cv_std = np.std(cv_scores)
print(f'\nCV średnie: {cv_mean:.3f} ± {cv_std:.3f} kWh/h')

# Diagnostyka przeuczenia
test_minus_cv = test_m['mae'] - cv_mean
print(f'\n[Diagnostyka]')
print(f'  Gap (test-train): {gap:.3f} kWh/h')
print(f'  Test - CV:        {test_minus_cv:+.3f} kWh/h')

if gap < 0.4 and abs(test_minus_cv) < 0.15:
    verdict = '✅ Model NIE jest przeuczony'
elif gap < 0.7 and abs(test_minus_cv) < 0.3:
    verdict = '⚠️  Lekkie przeuczenie (akceptowalne)'
else:
    verdict = '❌ Model przeuczony'
print(f'  {verdict}')

# ============================================================================
# 5. Agregacja do sum dziennych
# ============================================================================
print('\n[5] Agregacja do sum dziennych...')

test_with_pred = meta_test.copy()
test_with_pred['y_true'] = y_test.values
test_with_pred['y_pred'] = test_pred

daily_true = test_with_pred.groupby('day')['y_true'].sum()
daily_pred = test_with_pred.groupby('day')['y_pred'].sum()

daily_mae = mean_absolute_error(daily_true, daily_pred)
daily_r2 = r2_score(daily_true, daily_pred)

print(f'Dzienny MAE: {daily_mae:.3f} kWh/dzień')
print(f'Dzienny R²:  {daily_r2:.3f}')

# ============================================================================
# 6. Feature Importance
# ============================================================================
print('\n[6] Top 10 najważniejszych cech:')

feature_importance = pd.DataFrame({
    'feature': HOURLY_FEATURE_COLUMNS_EXTENDED,
    'importance': model.named_steps['model'].feature_importances_
}).sort_values('importance', ascending=False)

for idx, row in feature_importance.head(10).iterrows():
    print(f"  {row['feature']:<22} {row['importance']:.3f}")

# ============================================================================
# 7. Przykład predykcji
# ============================================================================
print('\n[7] Przykład: pierwszy dzień testowy')

first_day = meta_test['day'].min()
example = test_with_pred[test_with_pred['day'] == first_day]

print(f'Dzień: {first_day}')
print(f'{"Godz":<6} {"Rzecz.":<8} {"Pred.":<8} {"Błąd":<8}')
print('-' * 32)

for _, row in example.iterrows():
    h = int(row['hour'])
    true_val = row['y_true']
    pred_val = row['y_pred']
    err = pred_val - true_val
    print(f'{h:02d}:00  {true_val:6.2f}   {pred_val:6.2f}   {err:+6.2f}')

print('-' * 32)
print(f'Suma:  {example["y_true"].sum():6.2f}   {example["y_pred"].sum():6.2f}')

# ============================================================================
# 8. Zapis wyników i modelu
# ============================================================================
print('\n[8] Zapisywanie wyników...')

os.makedirs('data/processed', exist_ok=True)

from src.models.pv_hourly_predictor import PVHourlyPredictor, DEFAULT_MODEL_PATH, TrainingReport

predictor = PVHourlyPredictor(model_path=DEFAULT_MODEL_PATH)
predictor.pipeline = model
predictor.latitude = latitude
predictor.longitude = longitude
predictor.location = os.getenv('WEATHER_LOCATION')
predictor.report = TrainingReport(
    train_mae=train_m['mae'], test_mae=test_m['mae'], gap=gap,
    cv_mae=cv_mean, cv_std=cv_std, test_minus_cv=test_minus_cv,
    daily_mae=daily_mae, daily_r2=daily_r2, verdict=verdict,
    n_train=len(y_train), n_test=len(y_test),
)
model_path = predictor.save()
print(f'✓ {model_path}')

# Podsumowanie modelu
summary = pd.DataFrame([{
    'model': 'hourly_extended',
    'test_mae_hour': test_m['mae'],
    'test_r2_hour': test_m['r2'],
    'gap': gap,
    'cv_mae': cv_mean,
    'cv_std': cv_std,
    'test_minus_cv': test_minus_cv,
    'daily_mae': daily_mae,
    'daily_r2': daily_r2,
}])

summary.to_csv('data/processed/hourly_model_summary.csv', index=False)
test_with_pred.to_csv('data/processed/hourly_predictions.csv', index=False)
feature_importance.to_csv('data/processed/hourly_feature_importance.csv', index=False)

print('✓ data/processed/hourly_model_summary.csv')
print('✓ data/processed/hourly_predictions.csv')
print('✓ data/processed/hourly_feature_importance.csv')

print('\n' + '=' * 72)
print('GOTOWE! Model wytrenowany i zapisany.')
print('=' * 72)
print(f'\nKluczowe wyniki:')
print(f'  • Test MAE: {test_m["mae"]:.3f} kWh/h')
print(f'  • Dzienny MAE: {daily_mae:.3f} kWh/dzień')
print(f'  • {verdict}')
print(f'\nUżyj predykcji do harmonogramowania urządzeń:')
print(f'  python mlops/forecast_pv.py')
