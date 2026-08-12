"""
Odczyty licznika (portal Tauron) — IV–V 2025.

Dane z licznika od 21.04.2025; maj 2025 = pełny miesiąc (zgodnie z rozliczeniem).
Uzupełnia luki FoxESS API w maju.

Uzupełnij wartości za 21–30.04.2025 z portalu licznika, jeśli masz inne niż poniżej.

Uruchomienie:
    python scripts/init_meter_readings_table.py
    python scripts/add_meter_readings_2025.py
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')

# Maj 2025 — z rozliczenia Tauron (odczyt 31/05/2025)
MAY_2025 = {
    'period_start': '2025-05-01',
    'period_end': '2025-05-31',
    'import_kwh': 34.0,
    'export_kwh': 54.0,
    'import_zone1_kwh': 11.0,
    'import_zone2_kwh': 23.0,
    'export_zone1_kwh': 23.0,
    'export_zone2_kwh': 31.0,
    'source': 'licznik_tauron',
    'notes': 'Rozliczenie 05.2025 | pełny miesiąc | uzupełnia lukę FoxESS 12–26.05',
}

# 21–30.04.2025 — zaimportowane z CSV (scripts/import_meter_csv.py)
# Nie nadpisuj — źródło kanoniczne: licznik_tauron_csv


def upsert(row: dict) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        '''
        INSERT OR REPLACE INTO meter_readings (
            period_start, period_end, import_kwh, export_kwh,
            import_zone1_kwh, import_zone2_kwh, export_zone1_kwh, export_zone2_kwh,
            source, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            row['period_start'], row['period_end'],
            row.get('import_kwh'), row.get('export_kwh'),
            row.get('import_zone1_kwh'), row.get('import_zone2_kwh'),
            row.get('export_zone1_kwh'), row.get('export_zone2_kwh'),
            row['source'], row.get('notes'),
        ),
    )
    conn.commit()
    conn.close()


def main():
    print('ℹ️  Maj i kwiecień 2025 — użyj import_meter_csv.py (źródło: licznik_tauron_csv).')
    print('    Ten skrypt pozostawiony jako szablon; nie nadpisuje danych z CSV.')


if __name__ == '__main__':
    main()
