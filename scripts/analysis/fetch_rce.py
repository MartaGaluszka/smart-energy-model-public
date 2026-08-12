"""
Pobiera ceny RCE z API PSE i zapisuje do rce_prices.

Uruchomienie:
    python scripts/fetch_rce.py
    python scripts/fetch_rce.py --start 2026-05-01 --end 2026-05-31
"""

import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.data.rce_api import fetch_rce_range, save_rce_to_db

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')


def main():
    parser = argparse.ArgumentParser(description='Pobierz RCE z API PSE → rce_prices')
    parser.add_argument('--start', default='2026-05-01', help='Data początkowa (YYYY-MM-DD)')
    parser.add_argument('--end', default='2026-05-31', help='Data końcowa (YYYY-MM-DD)')
    parser.add_argument('--db', default=DB_PATH, help='Ścieżka do bazy SQLite')
    args = parser.parse_args()

    print('=' * 70)
    print('PSE RCE → rce_prices')
    print(f'Okres: {args.start} – {args.end}')
    print('=' * 70)

    df = fetch_rce_range(args.start, args.end)
    if df.empty:
        print('❌ Brak danych RCE z API PSE dla podanego okresu')
        sys.exit(1)

    n = save_rce_to_db(df, args.db)
    days = df['business_date'].nunique()
    print(f'✅ Pobrano {len(df)} rekordów (15-min) z {days} dni')
    print(f'✅ Zapisano {n} wierszy do rce_prices')
    print(f'   RCE min/max: {df["rce_pln_kwh"].min():.4f} – {df["rce_pln_kwh"].max():.4f} zł/kWh')
    print(f'   Średnia: {df["rce_pln_kwh"].mean():.4f} zł/kWh')

    from src.data.rcem import update_rcem_from_hourly
    start_month = args.start[:7]
    end_month = args.end[:7]
    nm = update_rcem_from_hourly(args.db, start_month, end_month)
    if nm:
        print(f'✅ Zaktualizowano RCEm (computed) dla {nm} miesięcy')

    print('\n💡 Kalkulator depozytu:')
    print(f'   python scripts/calculate_prosumer_deposit.py --start {args.start} --end {args.end}')
    print('   python scripts/fetch_rcem.py --import-seed   # oficjalne RCEm PSE')


if __name__ == '__main__':
    main()
