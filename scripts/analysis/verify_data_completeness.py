"""
Pokaż rozkład danych po naprawie filtra artefaktów
"""

import pandas as pd
from src.features.pv_features import load_training_frame

db_path = '/path/to/smart-energy-model/data/energy_model.db'

# Wczytaj pełne dane treningowe
df = load_training_frame(db_path, start_date='2025-06-01', end_date='2026-06-30')

print('='*80)
print('PODSUMOWANIE DANYCH PO NAPRAWIE FILTRA ARTEFAKTÓW')
print('='*80)

# Grupuj po miesiącach
df['month'] = pd.to_datetime(df['day']).dt.to_period('M')
monthly_counts = df.groupby('month').size()

print('\nLiczba dni w każdym miesiącu:')
for month, count in monthly_counts.items():
    print(f'  {month}: {count} dni')

print(f'\nŁącznie: {len(df)} dni')
print(f'Zakres: {df["day"].min()} do {df["day"].max()}')

# Sprawdź styczeń i luty szczegółowo
jan_feb = df[df['day'].between('2026-01-01', '2026-02-28')]
print(f'\n📅 Styczeń i Luty 2026: {len(jan_feb)} dni')
print(f'   Styczeń: {len(df[df["day"].between("2026-01-01", "2026-01-31")])} dni')
print(f'   Luty: {len(df[df["day"].between("2026-02-01", "2026-02-28")])} dni')

# Pokaż przykładowe wartości PV
print(f'\nProdukcja PV w styczniu/lutym:')
print(f'   Średnia: {jan_feb["pv_kwh_daytime"].mean():.2f} kWh')
print(f'   Min: {jan_feb["pv_kwh_daytime"].min():.2f} kWh')
print(f'   Max: {jan_feb["pv_kwh_daytime"].max():.2f} kWh')
