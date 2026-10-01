"""
Import / obliczenie RCEm (miesięczna cena PSE) → rcem_prices.

Uruchomienie:
    python scripts/analysis/fetch_rcem.py --fetch-pse
    python scripts/analysis/fetch_rcem.py --import-seed
    python scripts/analysis/fetch_rcem.py --compute-from-rce --start 2026-01 --end 2026-05
    python scripts/analysis/fetch_rcem.py --list
"""

import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.data.rcem import (
    RcEmNotPublished,
    compute_rcem_from_hourly,
    get_rcem,
    import_seed_to_db,
    list_rcem,
    sync_official_rcem,
    update_rcem_from_hourly,
)

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')


def main():
    parser = argparse.ArgumentParser(description='RCEm miesięczna (PSE) → rcem_prices')
    parser.add_argument('--db', default=DB_PATH)
    parser.add_argument(
        '--fetch-pse',
        action='store_true',
        help='Pobierz tabelę RCEm z pse.pl i zapisz miesiące w otwartym oknie korekty (12 miesięcy)',
    )
    parser.add_argument('--as-of', default=None, help='Data odniesienia YYYY-MM-DD (domyślnie dziś)')
    parser.add_argument('--import-seed', action='store_true', help='Zaimportuj oficjalne RCEm z data/rcem_pse_seed.json')
    parser.add_argument('--compute-from-rce', action='store_true', help='Oblicz średnią z rce_prices w bazie')
    parser.add_argument('--start', default='2026-01', help='Miesiąc początkowy YYYY-MM')
    parser.add_argument('--end', default='2026-05', help='Miesiąc końcowy YYYY-MM')
    parser.add_argument('--list', action='store_true', help='Pokaż tabelę rcem_prices')
    parser.add_argument('--month', default=None, help='Pokaż RCEm dla jednego miesiąca')
    args = parser.parse_args()

    if args.fetch_pse:
        as_of = datetime.strptime(args.as_of, '%Y-%m-%d').date() if args.as_of else None
        try:
            changes = sync_official_rcem(args.db, as_of=as_of)
        except RcEmNotPublished as exc:
            print(f'RCEm: {exc}', file=sys.stderr)
            sys.exit(1)
        if not changes:
            print('RCEm: brak miesięcy w otwartym oknie korekty')
        for row in changes:
            corr = row['corrected_rce_pln_mwh']
            corr_txt = f', korekta {corr:.2f} zł/MWh ({row["corrected_publication_date"]})' if corr else ''
            print(
                f'{row["period_month"]}: {row["rce_pln_mwh"]:.2f} zł/MWh'
                f' (publikacja {row["publication_date"]}){corr_txt} — {row["action"]}'
            )

    if args.import_seed:
        n = import_seed_to_db(args.db)
        print(f'✅ Zaimportowano {n} miesięcy RCEm (PSE) do rcem_prices')

    if args.compute_from_rce:
        n = update_rcem_from_hourly(args.db, args.start, args.end)
        print(f'✅ Obliczono RCEm z rce_prices dla {n} miesięcy ({args.start} – {args.end})')

    if args.month:
        r = get_rcem(args.month, args.db)
        if r:
            print(f'{args.month}: {r["rce_pln_mwh"]:.2f} zł/MWh ({r["rce_pln_kwh"]:.5f} zł/kWh) [{r["source"]}]')
        else:
            computed = compute_rcem_from_hourly(args.db, args.month)
            print(f'{args.month}: brak w bazie' + (f', z RCE godzinowej ≈ {computed:.2f} zł/MWh' if computed else ''))

    if args.list:
        df = list_rcem(args.db)
        if df.empty:
            print('Brak rekordów — uruchom: python scripts/fetch_rcem.py --import-seed')
        else:
            print(df[['period_month', 'rce_pln_mwh', 'corrected_rce_pln_mwh', 'source']].to_string(index=False))

    if not any([args.fetch_pse, args.import_seed, args.compute_from_rce, args.list, args.month]):
        parser.print_help()


if __name__ == '__main__':
    main()
