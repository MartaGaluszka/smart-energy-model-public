"""
Sprawdzenie danych w bazie dla stycznia i lutego 2026
"""

import sqlite3
import pandas as pd

db_path = '/path/to/smart-energy-model/data/energy_model.db'

print('='*80)
print('SPRAWDZENIE BAZY DANYCH: Styczeń i Luty 2026')
print('='*80)

conn = sqlite3.connect(db_path)

# Sprawdź dane PV
print('\n1. Dane PV (foxess_data):')
query_pv = """
SELECT 
    DATE(timestamp) as day,
    COUNT(*) as records,
    SUM(pv_energy_kwh) as total_pv,
    MIN(timestamp) as first_record,
    MAX(timestamp) as last_record
FROM foxess_data
WHERE DATE(timestamp) BETWEEN '2026-01-01' AND '2026-02-28'
GROUP BY DATE(timestamp)
ORDER BY day
"""

pv_data = pd.read_sql_query(query_pv, conn)
print(f'\nZnalezionych dni: {len(pv_data)}')
print(pv_data.to_string())

# Sprawdź dane pogodowe
print('\n\n2. Dane pogodowe (weather_data):')
query_weather = """
SELECT 
    DATE(timestamp) as day,
    COUNT(*) as records,
    AVG(solar_radiation_wm2) as avg_radiation
FROM weather_data
WHERE DATE(timestamp) BETWEEN '2026-01-01' AND '2026-02-28'
  AND location = 'home'
GROUP BY DATE(timestamp)
ORDER BY day
"""

weather_data = pd.read_sql_query(query_weather, conn)
print(f'\nZnalezionych dni: {len(weather_data)}')
print(weather_data.to_string())

# Sprawdź które dni mają oba typy danych
print('\n\n3. Dni z obydwoma typami danych (PV + pogoda):')
pv_days = set(pv_data['day'])
weather_days = set(weather_data['day'])
both = pv_days.intersection(weather_days)
only_pv = pv_days - weather_days
only_weather = weather_days - pv_days

print(f'\nDni z PV i pogodą: {len(both)}')
print(f'Dni tylko z PV: {len(only_pv)}')
print(f'Dni tylko z pogodą: {len(only_weather)}')

if only_pv:
    print(f'\n⚠️  Dni z PV ale BEZ pogody: {sorted(only_pv)}')
if only_weather:
    print(f'\n⚠️  Dni z pogodą ale BEZ PV: {sorted(only_weather)}')

# Sprawdź filtr battery
print('\n\n4. Sprawdzenie filtra baterii:')
query_battery = """
SELECT 
    DATE(timestamp) as day,
    COUNT(*) as total_records,
    SUM(CASE WHEN battery_power_kw >= -0.1 THEN 1 ELSE 0 END) as filtered_records,
    SUM(pv_energy_kwh) as total_pv,
    SUM(CASE WHEN battery_power_kw >= -0.1 THEN pv_energy_kwh ELSE 0 END) as filtered_pv
FROM foxess_data
WHERE DATE(timestamp) BETWEEN '2026-01-01' AND '2026-02-28'
GROUP BY DATE(timestamp)
ORDER BY day
"""

battery_data = pd.read_sql_query(query_battery, conn)
print(battery_data.to_string())

conn.close()

print('\n' + '='*80)
print('DIAGNOZA')
print('='*80)

total_expected = 31 + 28  # Styczeń + Luty
total_found = len(pv_data)
print(f'\nOczekiwane dni: {total_expected}')
print(f'Znalezione dni z PV: {total_found}')
print(f'Brakujące dni: {total_expected - total_found}')

if total_found < total_expected:
    print(f'\n⚠️  PROBLEM: Brak {total_expected - total_found} dni danych!')
    print('   Możliwe przyczyny:')
    print('   1. Dane nie zostały pobrane z FoxESS API')
    print('   2. Problem z połączeniem/importem')
    print('   3. Dane zostały usunięte/nadpisane')
