"""
Analiza przykładowych dni oznaczonych jako artefakty
"""

import sqlite3
import pandas as pd

db_path = '/path/to/smart-energy-model/data/energy_model.db'

print('='*80)
print('ANALIZA DNI OZNACZONYCH JAKO ARTEFAKTY')
print('='*80)

# Pobierz dane dla kilku przykładowych dni
conn = sqlite3.connect(db_path)

query = """
SELECT
    date(timestamp) AS day,
    ROUND(SUM(COALESCE(pv_energy_kwh, 0)), 3) AS pv_kwh_total,
    ROUND(SUM(CASE WHEN pv_energy_kwh > 0 AND COALESCE(battery_power_kw, 0) >= -0.1 
        THEN pv_energy_kwh ELSE 0 END), 3) AS pv_kwh_solar_filtered,
    ROUND(SUM(CASE WHEN pv_energy_kwh < 0 THEN -pv_energy_kwh ELSE 0 END), 3) AS pv_kwh_artifact,
    ROUND(SUM(CASE 
        WHEN pv_energy_kwh > 0
         AND COALESCE(battery_power_kw, 0) >= -0.1
         AND cast(strftime('%H', timestamp) AS integer) BETWEEN 9 AND 16
        THEN pv_energy_kwh ELSE 0 
    END), 3) AS pv_kwh_daytime_9_16
FROM foxess_data
WHERE date(timestamp) BETWEEN '2026-01-01' AND '2026-02-28'
GROUP BY day
ORDER BY day
"""

df = pd.read_sql_query(query, conn)
conn.close()

# Sprawdź logikę _is_artifact_day
df['artifact_ratio'] = df['pv_kwh_artifact'] / df['pv_kwh_daytime_9_16'].replace(0, 0.1)
df['is_artifact'] = (df['pv_kwh_artifact'] >= 10.0) & (df['pv_kwh_artifact'] > df['pv_kwh_daytime_9_16'].clip(lower=0.5) * 3.5)

print(f'\nPrzegląd wszystkich dni ({len(df)} dni):')
print(f'Oznaczone jako artefakty: {df["is_artifact"].sum()}')
print(f'Dni OK: {(~df["is_artifact"]).sum()}')

print('\n' + '='*80)
print('PRZYKŁADY DNI ARTEFAKTÓW (pierwsze 10):')
print('='*80)
artifacts = df[df['is_artifact']]
print(artifacts[['day', 'pv_kwh_total', 'pv_kwh_solar_filtered', 'pv_kwh_artifact', 'pv_kwh_daytime_9_16', 'artifact_ratio']].head(10).to_string())

print('\n' + '='*80)
print('PRZYKŁADY DNI OK (pierwsze 10):')
print('='*80)
ok_days = df[~df['is_artifact']]
print(ok_days[['day', 'pv_kwh_total', 'pv_kwh_solar_filtered', 'pv_kwh_artifact', 'pv_kwh_daytime_9_16', 'artifact_ratio']].head(10).to_string())

print('\n' + '='*80)
print('DIAGNOZA:')
print('='*80)
print(f'''
Obecna logika _is_artifact_day:
  - artifact >= 10.0 kWh
  - artifact > max(pv_daytime, 0.5) * 3.5

Problem: Zimą (styczeń, luty) bateria rozładowuje się w nocy → duży artifact.
         Po zastosowaniu filtra baterii (battery_power >= -0.1) pv_daytime jest małe.
         Stosunek artifact/pv jest wysoki → dni są fałszywie oznaczane jako artefakty.

Rozwiązania:
  1. Zwiększyć próg artifact z 10.0 do 20.0 kWh (mniej restrykcyjny)
  2. Zwiększyć mnożnik z 3.5 do 5.0 lub więcej
  3. Całkowicie wyłączyć filtr artefaktów dla 2026 (dane po konfiguracji falownika)
  4. Użyć pv_kwh_solar_filtered zamiast pv_kwh_daytime w porównaniu
  5. Dodać warunek sezonowy (mniej restrykcyjny zimą)

Rekomendacja: Opcja 3 (wyłączenie filtra artefaktów dla 2026)
  - Artefakty były problemem w okresie 21.04-29.05.2025 (błędna konfiguracja falownika)
  - Od 30.05.2025 (PV_WEATHER_VALID_START) konfiguracja jest OK
  - Styczeń i luty 2026 to wiarygodne dane produkcyjne
''')
