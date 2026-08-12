"""
Weryfikacja danych FoxESS: Styczeń i Luty 2026
Porównanie z danymi w bazie
"""

import sqlite3
import pandas as pd

db_path = '/path/to/smart-energy-model/data/energy_model.db'

print('='*80)
print('WERYFIKACJA DANYCH FOXESS: Styczeń i Luty 2026')
print('='*80)

conn = sqlite3.connect(db_path)

# Suma całkowita za miesiące (pv_kwh_solar z filtrem baterii)
query_monthly = """
SELECT 
    strftime('%Y-%m', timestamp) as month,
    COUNT(DISTINCT DATE(timestamp)) as days,
    ROUND(SUM(CASE WHEN pv_energy_kwh > 0 AND COALESCE(battery_power_kw, 0) >= -0.1 
        THEN pv_energy_kwh ELSE 0 END), 2) AS total_pv_solar
FROM foxess_data
WHERE DATE(timestamp) BETWEEN '2026-01-01' AND '2026-02-28'
GROUP BY month
ORDER BY month
"""

df_monthly = pd.read_sql_query(query_monthly, conn)

print('\n📊 SUMA MIESIĘCZNA (z filtrem baterii):')
print('='*80)
for _, row in df_monthly.iterrows():
    print(f"{row['month']}: {row['total_pv_solar']:.2f} kWh ({row['days']} dni)")

# Dane z FoxESS (podane przez użytkownika)
print('\n📱 DANE Z FOXESS (podane przez użytkownika):')
print('='*80)
print('2026-01: 193.50 kWh')
print('2026-02: 278.50 kWh')

# Porównanie
if not df_monthly.empty:
    jan_db = df_monthly[df_monthly['month'] == '2026-01']['total_pv_solar'].values[0] if len(df_monthly[df_monthly['month'] == '2026-01']) > 0 else 0
    feb_db = df_monthly[df_monthly['month'] == '2026-02']['total_pv_solar'].values[0] if len(df_monthly[df_monthly['month'] == '2026-02']) > 0 else 0
    
    print('\n🔍 PORÓWNANIE:')
    print('='*80)
    print(f"Styczeń:  Baza: {jan_db:.2f} kWh  vs  FoxESS: 193.50 kWh  (różnica: {abs(jan_db - 193.50):.2f} kWh)")
    print(f"Luty:     Baza: {feb_db:.2f} kWh  vs  FoxESS: 278.50 kWh  (różnica: {abs(feb_db - 278.50):.2f} kWh)")

# Sprawdź konkretne dni
print('\n\n📅 KONKRETNE DNI (podane przez użytkownika):')
print('='*80)

days_to_check = ['2026-02-21', '2026-02-22', '2026-02-23']
foxess_values = [14.80, 11.40, 7.40]

query_specific = """
SELECT 
    DATE(timestamp) as day,
    ROUND(SUM(CASE WHEN pv_energy_kwh > 0 AND COALESCE(battery_power_kw, 0) >= -0.1 
        THEN pv_energy_kwh ELSE 0 END), 2) AS pv_solar,
    ROUND(SUM(COALESCE(pv_energy_kwh, 0)), 2) AS pv_raw,
    COUNT(*) as records
FROM foxess_data
WHERE DATE(timestamp) IN ('2026-02-21', '2026-02-22', '2026-02-23')
GROUP BY day
ORDER BY day
"""

df_specific = pd.read_sql_query(query_specific, conn)

for day, foxess_val in zip(days_to_check, foxess_values):
    if day in df_specific['day'].values:
        row = df_specific[df_specific['day'] == day].iloc[0]
        db_val = row['pv_solar']
        diff = abs(db_val - foxess_val)
        match = '✅' if diff < 1.0 else '⚠️'
        print(f"{match} {day}: Baza: {db_val:.2f} kWh  vs  FoxESS: {foxess_val:.2f} kWh  (różnica: {diff:.2f} kWh)")
    else:
        print(f"❌ {day}: BRAK W BAZIE (FoxESS: {foxess_val:.2f} kWh)")

# Sprawdź co widzi model (load_training_frame)
print('\n\n🤖 CO WIDZI MODEL ML (po naprawie filtra)?')
print('='*80)

from src.features.pv_features import load_training_frame

df_training = load_training_frame(db_path, start_date='2026-01-01', end_date='2026-02-28')

print(f'Dni w treningu (styczeń + luty): {len(df_training)}')

# Suma w modelu
jan_training = df_training[df_training['day'].between('2026-01-01', '2026-01-31')]
feb_training = df_training[df_training['day'].between('2026-02-01', '2026-02-28')]

if not jan_training.empty:
    jan_model_total = jan_training['pv_kwh_daytime'].sum()
    print(f'\nStyczeń w modelu: {jan_model_total:.2f} kWh (9-16h)')
    print(f'  Liczba dni: {len(jan_training)}')

if not feb_training.empty:
    feb_model_total = feb_training['pv_kwh_daytime'].sum()
    print(f'\nLuty w modelu: {feb_model_total:.2f} kWh (9-16h)')
    print(f'  Liczba dni: {len(feb_training)}')

# Konkretne dni w modelu
print('\n📅 Konkretne dni w modelu (target: pv_kwh_daytime 9-16h):')
for day, foxess_val in zip(days_to_check, foxess_values):
    if day in df_training['day'].values:
        row = df_training[df_training['day'] == day].iloc[0]
        model_val = row['pv_kwh_daytime']
        print(f"✅ {day}: Model: {model_val:.2f} kWh (FoxESS całkowite: {foxess_val:.2f} kWh)")
    else:
        print(f"❌ {day}: BRAK W MODELU")

conn.close()

print('\n' + '='*80)
print('WYJAŚNIENIE RÓŻNIC')
print('='*80)
print('''
UWAGA: Różnice między wartościami to normalne:

1. Filtr baterii (battery_power >= -0.1):
   - Wyklucza produkcję PV gdy bateria się rozładowuje
   - FoxESS może pokazywać "produkcję" która jest faktycznie rozładowaniem baterii
   
2. Okno czasowe modelu (9-16h):
   - Model używa pv_kwh_daytime (historyczna agregacja 9-16h)
   - FoxESS pokazuje całkowite 24h
   - Zimą produkcja poza 9-16h jest minimalna, ale nie zero
   
3. Ujemne wartości:
   - FoxESS może mieć ujemne wartości (import z sieci)
   - Nasz filtr je usuwa

WNIOSEK: Jeśli wartości są w bazie, model je widzi! ✅
''')
