"""
Odczyt danych Tauron dla lutego 2026
"""

import sqlite3
import pandas as pd

db_path = '/path/to/smart-energy-model/data/energy_model.db'

conn = sqlite3.connect(db_path)

# Sprawdź odczyty licznika dla lutego 2026
query_meter = """
SELECT 
    period_start,
    period_end,
    import_kwh,
    export_kwh,
    import_zone1_kwh,
    import_zone2_kwh,
    export_zone1_kwh,
    export_zone2_kwh,
    source,
    notes
FROM meter_readings
WHERE period_start >= '2026-02-01' 
  AND period_end <= '2026-02-28'
ORDER BY period_start
"""

meter = pd.read_sql_query(query_meter, conn)

# Sprawdź faktury dla lutego 2026
query_bills = """
SELECT 
    bill_date,
    billing_period_start,
    billing_period_end,
    actual_zone1_kwh,
    actual_zone2_kwh,
    actual_total_kwh,
    energy_exported_kwh,
    bill_number
FROM tauron_bills
WHERE billing_period_start >= '2026-02-01' 
  AND billing_period_end <= '2026-02-28'
ORDER BY billing_period_start
"""

bills = pd.read_sql_query(query_bills, conn)

conn.close()

print('='*80)
print('DANE TAURON - LUTY 2026')
print('='*80)

if not meter.empty:
    print('\n📊 ODCZYTY LICZNIKA (meter_readings):')
    print('='*80)
    for _, row in meter.iterrows():
        print(f"\nOkres: {row['period_start']} → {row['period_end']}")
        print(f"  Import (pobór):  {row['import_kwh']:.2f} kWh")
        print(f"    - Strefa T1:   {row['import_zone1_kwh']:.2f} kWh")
        print(f"    - Strefa T2:   {row['import_zone2_kwh']:.2f} kWh")
        print(f"  Eksport (oddanie): {row['export_kwh']:.2f} kWh")
        print(f"    - Strefa T1:   {row['export_zone1_kwh']:.2f} kWh")
        print(f"    - Strefa T2:   {row['export_zone2_kwh']:.2f} kWh")
        print(f"  Źródło: {row['source']}")
else:
    print('\n⚠️  Brak danych w meter_readings dla lutego 2026')

if not bills.empty:
    print('\n\n📄 FAKTURY (tauron_bills):')
    print('='*80)
    for _, row in bills.iterrows():
        print(f"\nOkres: {row['billing_period_start']} → {row['billing_period_end']}")
        print(f"  Import (pobór):  {row['actual_total_kwh']:.2f} kWh")
        print(f"    - Strefa T1:   {row['actual_zone1_kwh']:.2f} kWh")
        print(f"    - Strefa T2:   {row['actual_zone2_kwh']:.2f} kWh")
        print(f"  Eksport (oddanie): {row['energy_exported_kwh']:.2f} kWh")
        print(f"  Nr faktury: {row['bill_number']}")
else:
    print('\n⚠️  Brak faktur w tauron_bills dla lutego 2026')

# Podsumowanie
print('\n\n' + '='*80)
print('PODSUMOWANIE:')
print('='*80)

if not meter.empty:
    total_import = meter['import_kwh'].sum()
    total_export = meter['export_kwh'].sum()
    print(f'\n📊 LUTY 2026 (z licznika):')
    print(f'  ⬇️  Import (Tauron → Dom):  {total_import:.2f} kWh')
    print(f'  ⬆️  Eksport (Dom → Tauron): {total_export:.2f} kWh')
    print(f'  📊 Bilans:                  {total_export - total_import:.2f} kWh')
elif not bills.empty:
    total_import = bills['actual_total_kwh'].sum()
    total_export = bills['energy_exported_kwh'].sum()
    print(f'\n📄 LUTY 2026 (z faktury):')
    print(f'  ⬇️  Import (Tauron → Dom):  {total_import:.2f} kWh')
    print(f'  ⬆️  Eksport (Dom → Tauron): {total_export:.2f} kWh')
    print(f'  📊 Bilans:                  {total_export - total_import:.2f} kWh')
else:
    print('\n❌ Brak danych dla lutego 2026')
