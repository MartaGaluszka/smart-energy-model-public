"""
Analiza: Ładowanie baterii vs Rozładowanie
Przykłady z 5:30 i 5:43
"""

import sqlite3
import pandas as pd

db_path = '/path/to/smart-energy-model/data/energy_model.db'

print('='*80)
print('ANALIZA: ŁADOWANIE BATERII (battery_power > 0)')
print('='*80)

print('\n📱 DANE Z FOXESS APP:')
print('='*80)
print('\n🔋 5:30 - Ładowanie baterii 2.12 kW:')
print('   Battery charging: 2.12 kW (dodatnie!)')
print('   Grid import:      0.19 kW')
print('   Consumption:      8.08 kW')
print('   Bilans: PV ≈ 8.08 + 2.12 - 0.19 = 10.01 kW (duża produkcja!)')

print('\n🔋 5:43 - Ładowanie baterii 10.45 kW:')
print('   Battery charging: 10.45 kW (DUŻO!)')
print('   Grid import:      13.36 kW (DUŻO!)')
print('   Consumption:      2.40 kW')
print('   Bilans: 10.45 + 2.40 = 12.85 kW ≈ Import 13.36 kW')
print('   → To jest FORCED CHARGING z sieci (tania strefa G12w)!')

# Sprawdź co się dzieje w bazie dla różnych godzin rano
print('\n\n' + '='*80)
print('PRZYKŁADY Z BAZY - Luty 2026, różne godziny rano:')
print('='*80)

conn = sqlite3.connect(db_path)

# Sprawdź różne scenariusze ładowania
query = """
SELECT 
    strftime('%Y-%m-%d %H:%M', timestamp) as time,
    ROUND(pv_power_kw, 2) as pv_power,
    ROUND(pv_energy_kwh, 3) as pv_energy,
    ROUND(battery_power_kw, 2) as battery_power,
    ROUND(load_power_kw, 2) as load_power,
    CASE 
        WHEN pv_energy_kwh > 0 AND battery_power_kw >= -0.1 THEN 'TAK ✅'
        ELSE 'NIE ❌'
    END as passes_filter,
    CASE
        WHEN battery_power_kw > 2.0 THEN '🔋 ŁADOWANIE'
        WHEN battery_power_kw > 0.1 THEN '🔋 słabe ładowanie'
        WHEN battery_power_kw >= -0.1 THEN '⚡ równowaga'
        ELSE '🔻 ROZŁADOWANIE'
    END as battery_status
FROM foxess_data
WHERE DATE(timestamp) BETWEEN '2026-02-01' AND '2026-02-28'
  AND strftime('%H', timestamp) IN ('05', '06', '07')
  AND (
      battery_power_kw > 2.0  -- silne ładowanie
      OR battery_power_kw < -1.0  -- silne rozładowanie
  )
ORDER BY RANDOM()
LIMIT 10
"""

df = pd.read_sql_query(query, conn)

print('\nCzas         | PV(kW) | PV(kWh) | Bat(kW) | Load | Filtr  | Status')
print('-' * 85)

for _, row in df.iterrows():
    print(f"{row['time']} | {row['pv_power']:6.2f} | {row['pv_energy']:7.3f} | {row['battery_power']:7.2f} | {row['load_power']:4.2f} | {row['passes_filter']} | {row['battery_status']}")

# Statystyki dla różnych stanów baterii
print('\n\n' + '='*80)
print('STATYSTYKI: Jak filtr działa dla różnych stanów baterii?')
print('='*80)

query_stats = """
SELECT 
    CASE
        WHEN battery_power_kw > 2.0 THEN 'ŁADOWANIE (>2 kW)'
        WHEN battery_power_kw > 0.1 THEN 'Słabe ładowanie'
        WHEN battery_power_kw >= -0.1 THEN 'Równowaga'
        WHEN battery_power_kw >= -2.0 THEN 'Słabe rozładowanie'
        ELSE 'ROZŁADOWANIE (<-2 kW)'
    END as battery_state,
    COUNT(*) as total_records,
    SUM(CASE WHEN pv_energy_kwh > 0 AND battery_power_kw >= -0.1 THEN 1 ELSE 0 END) as passed_filter,
    ROUND(AVG(battery_power_kw), 2) as avg_battery_kw,
    ROUND(SUM(pv_energy_kwh), 2) as total_pv_kwh
FROM foxess_data
WHERE DATE(timestamp) BETWEEN '2026-01-01' AND '2026-02-28'
  AND strftime('%H', timestamp) BETWEEN '05' AND '08'
GROUP BY battery_state
ORDER BY avg_battery_kw DESC
"""

stats = pd.read_sql_query(query_stats, conn)
conn.close()

print('\nStan baterii         | Pomiarów | Przeszło filtr | % | Śr. bat | Suma PV')
print('-' * 85)

for _, row in stats.iterrows():
    total = row['total_records']
    passed = row['passed_filter']
    pct = (passed / total * 100) if total > 0 else 0
    
    print(f"{row['battery_state']:20} | {total:8} | {passed:14} | {pct:5.1f}% | {row['avg_battery_kw']:7.2f} | {row['total_pv_kwh']:7.2f}")

print('\n\n' + '='*80)
print('KLUCZOWE WNIOSKI:')
print('='*80)
print('''
1. ✅ ŁADOWANIE BATERII (battery_power > 0) PRZECHODZI przez filtr!
   - battery_power = +2.12 kW → FILTR: TAK ✅
   - battery_power = +10.45 kW → FILTR: TAK ✅
   - Model WIDZI te pomiary i UCZY SIĘ z nich!

2. ❌ ROZŁADOWANIE BATERII (battery_power < -0.1) NIE PRZECHODZI:
   - battery_power = -1.54 kW → FILTR: NIE ❌
   - Model NIE WIDZI tych pomiarów

3. 🎯 DLACZEGO TAK?
   Filtr: battery_power >= -0.1
   
   ✅ Ładowanie (+):    Energia WPŁYWA do baterii
                        PV może ładować baterię I zasilać dom
                        pv_energy_kwh = RZECZYWISTA produkcja ✅
   
   ❌ Rozładowanie (-): Energia WYPŁYWA z baterii
                        FoxESS może błędnie zapisać część jako "PV"
                        pv_energy_kwh zawiera ARTEFAKT ❌

4. 📊 Scenariusze rano (5:00-8:00):
   
   a) 5:30 - Wschód słońca, PV startuje:
      • PV = 10 kW (duża produkcja)
      • Battery = +2.12 kW (ładowanie z PV)
      • Load = 8.08 kW
      → Model WIDZI ten pomiar ✅
      
   b) 5:43 - Jeszcze ciemno, forced charging:
      • PV = 0 kW (brak słońca)
      • Battery = +10.45 kW (ładowanie Z SIECI!)
      • Grid import = 13.36 kW (tania strefa G12w)
      → Model WIDZI, ale pv_energy_kwh = 0 (brak PV)
      
5. 💡 WNIOSEK KOŃCOWY:
   Filtr battery_power >= -0.1 to:
   ✅ PRZEPUSZCZA: Ładowanie i równowagę (produkcja PV jest czysta)
   ❌ BLOKUJE: Rozładowanie (może zawierać artefakty)
   
   To jest DOKŁADNIE to czego chcemy! 🎯
''')
