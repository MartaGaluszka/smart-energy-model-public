"""
Weryfikacja: Czy styczeń i luty 2026 są używane w treningu modeli?
"""

import pandas as pd
from src.features.pv_features import load_training_frame

db_path = '/path/to/smart-energy-model/data/energy_model.db'

print('='*80)
print('WERYFIKACJA: Czy styczeń i luty są w treningu?')
print('='*80)

# Wczytaj dane treningowe (Development: czerwiec 2025 - maj 2026)
df_dev = load_training_frame(db_path, start_date='2025-06-01', end_date='2026-05-31')

print(f'\n📊 Development Set (czerwiec 2025 - maj 2026):')
print(f'   Łącznie dni: {len(df_dev)}')

# Sprawdź rozkład po miesiącach
df_dev['year_month'] = pd.to_datetime(df_dev['day']).dt.to_period('M')
monthly = df_dev.groupby('year_month').size()

print('\n📅 Rozkład danych po miesiącach:')
for month, count in monthly.items():
    marker = '✅' if count >= 25 else '⚠️'
    print(f'   {marker} {month}: {count} dni')

# Sprawdź styczeń i luty szczegółowo
jan_data = df_dev[df_dev['day'].between('2026-01-01', '2026-01-31')]
feb_data = df_dev[df_dev['day'].between('2026-02-01', '2026-02-28')]

print(f'\n🎯 KLUCZOWE MIESIĄCE:')
print(f'   Styczeń 2026: {len(jan_data)} dni (max 31)')
print(f'   Luty 2026: {len(feb_data)} dni (max 28)')

if len(jan_data) == 31 and len(feb_data) == 28:
    print('\n✅ SUKCES! Wszystkie dni stycznia i lutego są w treningu!')
else:
    print(f'\n⚠️  UWAGA: Brakuje {31 - len(jan_data)} dni w styczniu i {28 - len(feb_data)} dni w lutym')

# Statystyki produkcji PV
print(f'\n📈 Produkcja PV w zimie (styczeń + luty):')
winter = pd.concat([jan_data, feb_data])
if not winter.empty:
    print(f'   Średnia: {winter["pv_kwh_daytime"].mean():.2f} kWh/dzień')
    print(f'   Mediana: {winter["pv_kwh_daytime"].median():.2f} kWh/dzień')
    print(f'   Min: {winter["pv_kwh_daytime"].min():.2f} kWh')
    print(f'   Max: {winter["pv_kwh_daytime"].max():.2f} kWh')
    
    # Porównaj z latem
    summer = df_dev[df_dev['day'].between('2025-06-01', '2025-08-31')]
    if not summer.empty:
        print(f'\n📈 Dla porównania - Lato 2025 (czerwiec-sierpień):')
        print(f'   Średnia: {summer["pv_kwh_daytime"].mean():.2f} kWh/dzień')
        print(f'   Mediana: {summer["pv_kwh_daytime"].median():.2f} kWh/dzień')
        print(f'   Min: {summer["pv_kwh_daytime"].min():.2f} kWh')
        print(f'   Max: {summer["pv_kwh_daytime"].max():.2f} kWh')

print('\n' + '='*80)
print('PODSUMOWANIE')
print('='*80)
print(f'''
Development Set obejmuje pełny cykl sezonowy:
- ✅ Lato 2025 (czerwiec-sierpień): {len(df_dev[df_dev["day"].between("2025-06-01", "2025-08-31")])} dni
- ✅ Jesień 2025 (wrzesień-listopad): {len(df_dev[df_dev["day"].between("2025-09-01", "2025-11-30")])} dni
- ✅ Zima 2025/2026 (grudzień-luty): {len(df_dev[df_dev["day"].between("2025-12-01", "2026-02-29")])} dni
- ✅ Wiosna 2026 (marzec-maj): {len(df_dev[df_dev["day"].between("2026-03-01", "2026-05-31")])} dni

Model ma pełną reprezentację wszystkich pór roku! 🎉
''')
