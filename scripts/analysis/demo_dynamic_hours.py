#!/usr/bin/env python
"""
Demo: Model godzinowy z dynamicznymi godzinami produkcji.

Pokazuje jak cechy wschodu/zachodu słońca poprawiają predykcję.
"""
import os
os.environ['ML_TRAIN_START'] = '2025-06-01'

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd

from src.features.pv_features_hourly_extended import (
    load_hourly_training_frame_extended,
    HOURLY_FEATURE_COLUMNS_EXTENDED,
)

print('=' * 72)
print('DEMO: Dynamiczne godziny produkcji PV (wschód/zachód słońca)')
print('=' * 72)

# Wczytaj dane z rozszerzonymi cechami
print('\n[1] Ładowanie danych z cechami słonecznymi...')
print('    (godziny 5-21h, filtrowanie po rzeczywistej produkcji)')

# Pobierz współrzędne z .env lub użyj domyślnych
latitude = float(os.getenv('WEATHER_LAT', '50.06'))
longitude = float(os.getenv('WEATHER_LON', '19.94'))

print(f'    Lokalizacja: {latitude}°N, {longitude}°E')

df = load_hourly_training_frame_extended(
    start_date='2025-06-01',
    end_date='2026-07-09',
    latitude=latitude,
    longitude=longitude,
)

print(f'\n✓ Wczytano {len(df)} rekordów godzinowych')
print(f'✓ Dni: {df["day"].nunique()}')

# Pokaż przykłady dla różnych pór roku
print('\n[2] Przykłady wschodu/zachodu słońca:')
print('=' * 72)

examples = [
    ('2025-06-21', 'Letnie przesilenie'),
    ('2025-12-21', 'Zimowe przesilenie'),
    ('2026-03-20', 'Równonoc wiosenna'),
]

for date_str, label in examples:
    day_data = df[df['day'] == date_str]
    if not day_data.empty:
        sunrise = day_data['sunrise_hour'].iloc[0]
        sunset = day_data['sunset_hour'].iloc[0]
        day_length = day_data['day_length_hours'].iloc[0]
        first_hour = day_data['hour'].min()
        last_hour = day_data['hour'].max()
        total_pv = day_data['pv_kwh_hour'].sum()
        
        print(f'\n{label} ({date_str}):')
        print(f'  Wschód słońca:    {int(sunrise):02d}:{int((sunrise % 1) * 60):02d}')
        print(f'  Zachód słońca:    {int(sunset):02d}:{int((sunset % 1) * 60):02d}')
        print(f'  Długość dnia:     {day_length:.1f}h')
        print(f'  Produkcja PV:     {first_hour}:00 - {last_hour}:00 ({last_hour-first_hour+1}h)')
        print(f'  Suma produkcji:   {total_pv:.2f} kWh')

# Statystyki miesięczne
print('\n[3] Statystyki miesięczne:')
print('=' * 72)

monthly = df.groupby(df['day'].str[:7]).agg({
    'sunrise_hour': 'mean',
    'sunset_hour': 'mean',
    'day_length_hours': 'mean',
    'hour': ['min', 'max'],
    'pv_kwh_hour': 'sum',
}).round(2)

monthly.columns = ['Wschód', 'Zachód', 'Długość dnia', 'PV od', 'PV do', 'Suma PV']
print(monthly.to_string())

# Porównanie: sztywne 9-16h vs dynamiczne
print('\n[4] Porównanie: sztywne 9-16h vs dynamiczne godziny:')
print('=' * 72)

# Ile produkcji tracimy przy sztywnych 9-16h?
df_summer = df[df['day'].str[:7] == '2025-06']  # Czerwiec
df_winter = df[df['day'].str[:7] == '2026-01']  # Styczeń

def calc_loss(df_month, month_name):
    total = df_month['pv_kwh_hour'].sum()
    in_9_16 = df_month[(df_month['hour'] >= 9) & (df_month['hour'] <= 16)]['pv_kwh_hour'].sum()
    lost = total - in_9_16
    lost_pct = (lost / total * 100) if total > 0 else 0
    
    print(f'{month_name}:')
    print(f'  Produkcja całkowita:  {total:.1f} kWh')
    print(f'  Produkcja 9-16h:      {in_9_16:.1f} kWh')
    print(f'  STRATA:               {lost:.1f} kWh ({lost_pct:.1f}%)')

calc_loss(df_summer, 'Czerwiec 2025 (lato)')
print()
calc_loss(df_winter, 'Styczeń 2026 (zima)')

# Nowe cechy
print('\n[5] Nowe cechy słoneczne dostępne w modelu:')
print('=' * 72)

new_features = [
    'sunrise_hour', 'sunset_hour', 'day_length_hours',
    'hours_since_sunrise', 'hours_until_sunset',
    'sun_position', 'is_daylight'
]

print('Przykład dla jednej godziny (2025-06-21, 12:00):')
example_row = df[(df['day'] == '2025-06-21') & (df['hour'] == 12)].iloc[0] if len(df[(df['day'] == '2025-06-21') & (df['hour'] == 12)]) > 0 else None

if example_row is not None:
    for feat in new_features:
        value = example_row[feat]
        print(f'  {feat:<22} = {value:.3f}')

print('\n' + '=' * 72)
print('GOTOWE! Dane przygotowane z cechami słonecznymi.')
print('=' * 72)
print('\nKolejne kroki:')
print('  1. Wytrenuj model z HOURLY_FEATURE_COLUMNS_EXTENDED')
print('  2. Porównaj MAE z modelem bazowym (9-16h)')
print('  3. Zobacz czy predykcje są lepsze w skrajnych porach roku')
