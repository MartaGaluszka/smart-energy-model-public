"""
Diagnoza: Który filtr usuwa dane stycznia i lutego z treningu?
"""

import os
import sqlite3
from datetime import date

import pandas as pd
from src.data.household_context import is_pv_weather_valid
from src.features.pv_features import load_training_frame, _is_artifact_day
from src.data.weather_api import load_daily_weather, load_daily_pv, load_daily_pv_daytime

db_path = '/path/to/smart-energy-model/data/energy_model.db'
start_date = '2026-01-01'
end_date = '2026-02-28'

print('='*80)
print('DIAGNOZA FILTRÓW — Styczeń i Luty 2026')
print('='*80)

# Krok 1: Wczytaj surowe dane
print('\n1. Surowe dane:')
latitude = float(os.getenv('WEATHER_LAT', '50.06'))
longitude = float(os.getenv('WEATHER_LON', '19.94'))

weather = load_daily_weather(db_path, start_date, end_date, use_dynamic_hours=True,
                             latitude=latitude, longitude=longitude)
pv = load_daily_pv(db_path, start_date, end_date)
pv_day = load_daily_pv_daytime(db_path, start_date, end_date)

# Połącz dane
df = weather.merge(pv, on='day').merge(pv_day, on='day')
print(f'Liczba dni po połączeniu: {len(df)}')

# Krok 2: Sprawdź każdy filtr osobno
print('\n2. Sprawdzenie filtrów:')

# Filtr 1: is_pv_weather_valid
valid_pv_weather = df['day'].apply(lambda d: is_pv_weather_valid(date.fromisoformat(d)))
print(f'  a) is_pv_weather_valid: {valid_pv_weather.sum()} / {len(df)} dni przeszło')
failed_pv_weather = df[~valid_pv_weather]['day'].tolist()
if failed_pv_weather:
    print(f'     ❌ Dni odrzucone: {failed_pv_weather[:5]}...' if len(failed_pv_weather) > 5 else f'     ❌ Dni odrzucone: {failed_pv_weather}')

# Filtr 2: _is_artifact_day
is_artifact = df.apply(_is_artifact_day, axis=1)
print(f'  b) ~_is_artifact_day: {(~is_artifact).sum()} / {len(df)} dni przeszło (artefakty: {is_artifact.sum()})')
artifact_days = df[is_artifact]['day'].tolist()
if artifact_days:
    print(f'     ⚠️  Dni z artefaktami: {artifact_days[:5]}...' if len(artifact_days) > 5 else f'     ⚠️  Dni z artefaktami: {artifact_days}')

# Filtr 3: pv_kwh_daytime not null
has_pv_daytime = df['pv_kwh_daytime'].notna()
print(f'  c) pv_kwh_daytime.notna(): {has_pv_daytime.sum()} / {len(df)} dni przeszło')
no_pv_daytime = df[~has_pv_daytime]['day'].tolist()
if no_pv_daytime:
    print(f'     ❌ Dni bez pv_kwh_daytime: {no_pv_daytime[:5]}...' if len(no_pv_daytime) > 5 else f'     ❌ Dni bez pv_kwh_daytime: {no_pv_daytime}')

# Filtr 4: radiation_daytime_kwh_m2 not null
has_radiation = df['radiation_daytime_kwh_m2'].notna()
print(f'  d) radiation_daytime_kwh_m2.notna(): {has_radiation.sum()} / {len(df)} dni przeszło')
no_radiation = df[~has_radiation]['day'].tolist()
if no_radiation:
    print(f'     ❌ Dni bez radiation_daytime_kwh_m2: {no_radiation[:5]}...' if len(no_radiation) > 5 else f'     ❌ Dni bez radiation_daytime_kwh_m2: {no_radiation}')

# Kombinacja wszystkich filtrów
all_valid = valid_pv_weather & ~is_artifact & has_pv_daytime & has_radiation
print(f'\n3. Wszystkie filtry łącznie: {all_valid.sum()} / {len(df)} dni przeszło')
failed = df[~all_valid]
print(f'\nOdrzucone dni: {len(failed)}')
if not failed.empty:
    print('Przykłady odrzuconych:')
    for idx, row in failed.head(10).iterrows():
        reasons = []
        if not is_pv_weather_valid(date.fromisoformat(row['day'])):
            reasons.append('PV_WEATHER_INVALID')
        if _is_artifact_day(row):
            reasons.append('ARTIFACT')
        if pd.isna(row['pv_kwh_daytime']):
            reasons.append('NO_PV_DAYTIME')
        if pd.isna(row['radiation_daytime_kwh_m2']):
            reasons.append('NO_RADIATION')
        print(f"  {row['day']}: {', '.join(reasons)}")

# Sprawdź co load_training_frame zwraca
print('\n4. Weryfikacja load_training_frame:')
trained = load_training_frame(db_path, start_date, end_date)
print(f'Wczytane dni przez load_training_frame: {len(trained)}')
print(f'\nZakres dat: {trained["day"].min()} do {trained["day"].max()}')
