"""
Analiza prostej linii w styczniu i lutym
"""

import pandas as pd
import numpy as np
from src.features.pv_features import load_training_frame

# Load data
db_path = '/path/to/smart-energy-model/data/energy_model.db'
df = load_training_frame(db_path, '2025-12-01', '2026-02-28', 'home')

print('='*80)
print('ANALIZA DANYCH: Grudzień 2025 - Luty 2026')
print('='*80)

# Analiza miesięczna
df['month'] = pd.to_datetime(df['day']).dt.to_period('M')

for month in sorted(df['month'].unique()):
    month_data = df[df['month'] == month]
    
    print(f'\n📅 {month}:')
    print(f'  Liczba dni: {len(month_data)}')
    print(f'  PV produkcja:')
    print(f'    Min: {month_data["pv_kwh"].min():.2f} kWh')
    print(f'    Max: {month_data["pv_kwh"].max():.2f} kWh')
    print(f'    Średnia: {month_data["pv_kwh"].mean():.2f} kWh')
    print(f'    Std: {month_data["pv_kwh"].std():.2f} kWh')
    
    # Sprawdź dni z zerową produkcją
    zero_days = (month_data['pv_kwh'] < 0.1).sum()
    print(f'    Dni z produkcją < 0.1 kWh: {zero_days} ({zero_days/len(month_data)*100:.1f}%)')
    
    # Sprawdź cechy kluczowe
    print(f'  Radiacja:')
    print(f'    Min: {month_data["radiation_daytime_kwh_m2"].min():.2f} kWh/m²')
    print(f'    Max: {month_data["radiation_daytime_kwh_m2"].max():.2f} kWh/m²')
    print(f'    Średnia: {month_data["radiation_daytime_kwh_m2"].mean():.2f} kWh/m²')
    
    # Sprawdź śnieg
    snow_days = month_data['snow_on_panels'].sum()
    print(f'  Dni ze śniegiem na panelach: {snow_days} ({snow_days/len(month_data)*100:.1f}%)')
    
    # Sprawdź mgłę
    fog_days = month_data['likely_fog_day'].sum()
    print(f'  Dni z mgłą: {fog_days} ({fog_days/len(month_data)*100:.1f}%)')

# Szczegółowe dane dla stycznia i lutego
print('\n' + '='*80)
print('SZCZEGÓŁY: Styczeń i Luty 2026')
print('='*80)

jan_feb = df[df['month'].isin([pd.Period('2026-01'), pd.Period('2026-02')])]

print(f'\nWszystkie wartości PV (styczeń-luty):')
print(jan_feb[['day', 'pv_kwh', 'radiation_daytime_kwh_m2', 'snow_on_panels']].to_string())

print('\n' + '='*80)
print('DIAGNOZA')
print('='*80)

# Czy wartości są stałe?
jan_data = df[df['month'] == pd.Period('2026-01')]
feb_data = df[df['month'] == pd.Period('2026-02')]

if len(jan_data) > 0:
    jan_unique = jan_data['pv_kwh'].nunique()
    print(f'\n📊 Styczeń 2026:')
    print(f'  Unikalnych wartości PV: {jan_unique}')
    if jan_unique < 3:
        print('  ⚠️  PROBLEM: Bardzo mało unikalnych wartości!')
        print(f'  Wartości: {sorted(jan_data["pv_kwh"].unique())}')

if len(feb_data) > 0:
    feb_unique = feb_data['pv_kwh'].nunique()
    print(f'\n📊 Luty 2026:')
    print(f'  Unikalnych wartości PV: {feb_unique}')
    if feb_unique < 3:
        print('  ⚠️  PROBLEM: Bardzo mało unikalnych wartości!')
        print(f'  Wartości: {sorted(feb_data["pv_kwh"].unique())}')
