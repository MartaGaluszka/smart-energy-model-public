"""
Import godzinowego eksportu licznika Tauron (CSV z portalu).

Przykład:
    source venv/bin/activate
    python scripts/import_meter_csv.py data/raw/meter/2025-05_licznik.csv

Domyślnie: plik z Downloads jeśli skopiowany do data/raw/meter/
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.data.import_meter_csv import import_meter_csv

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')

DEFAULT_CSV = 'data/raw/meter/2025-05_licznik.csv'


BENCHMARKS = {
    ('2025-05-01', '2025-05-31'): (34, 54, 'rozliczenie V 2025'),
    ('2025-04-25', '2025-04-30'): (1, 2, 'rozliczenie IV 2025 (25–30.04)'),
    ('2025-04-21', '2025-04-30'): (None, None, 'okres przed/po instalacji PV'),
}


def main():
    paths = sys.argv[1:] if len(sys.argv) > 1 else [DEFAULT_CSV]
    missing = [p for p in paths if not os.path.isfile(p)]
    if missing:
        print(f'❌ Brak pliku(ów): {", ".join(missing)}')
        print('   Użycie: python scripts/import_meter_csv.py <plik1.csv> [plik2.csv ...]')
        sys.exit(1)

    df, s = import_meter_csv(*paths, db_path=DB_PATH)

    print('=' * 70)
    print(f'Import licznika: {", ".join(paths)}')
    print(f'Wierszy godzinowych: {len(df)}')
    print('=' * 70)
    print(f'Okres: {s["period_start"]} – {s["period_end"]}')
    print(f'Pobór (import):  {s["import_kwh"]:.3f} kWh  '
          f'(T1 {s["import_zone1_kwh"]:.3f} + T2 {s["import_zone2_kwh"]:.3f})')
    print(f'Oddanie (export): {s["export_kwh"]:.3f} kWh  '
          f'(T1 {s["export_zone1_kwh"]:.3f} + T2 {s["export_zone2_kwh"]:.3f})')

    key = (s['period_start'], s['period_end'])
    bench = BENCHMARKS.get(key)
    if bench:
        exp_i, exp_e, label = bench
        print()
        print(f'📌 Porównanie z {label}:')
        if exp_i is not None:
            print(f'   Oczekiwano: pobór {exp_i} kWh, oddanie {exp_e} kWh')
            print(f'   Z licznika: pobór {s["import_kwh"]:.1f} kWh, oddanie {s["export_kwh"]:.1f} kWh')
            if abs(s['import_kwh'] - exp_i) < 0.5 and abs(s['export_kwh'] - exp_e) < 0.5:
                print('   ✅ Zgodne z rozliczeniem')
            else:
                print(f'   ⚠️  Różnica: pobór {abs(s["import_kwh"] - exp_i):.2f} kWh, '
                      f'oddanie {abs(s["export_kwh"] - exp_e):.2f} kWh')
        else:
            print('   Brak benchmarku rozliczeniowego — sumy z licznika powyżej')

    if s['period_start'] == '2025-04-21' and s['period_end'] == '2025-04-30':
        from src.data.import_meter_csv import aggregate_period
        sub = aggregate_period(df, '2025-04-25', '2025-04-30')
        print()
        print('📌 Podokres 25–30.04 (rozliczenie IV 2025):')
        print(f'   Pobór {sub["import_kwh"]:.3f} kWh, oddanie {sub["export_kwh"]:.3f} kWh '
              f'(oczekiwano 1 / 2 kWh)')


if __name__ == '__main__':
    main()
