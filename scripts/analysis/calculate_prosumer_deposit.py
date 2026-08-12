"""
Szacuje depozyt prosumencki: RCE godzinowa + RCEm miesięczna (PSE/Tauron).

Uruchomienie:
    python scripts/fetch_rce.py --start 2026-05-01 --end 2026-05-31
    python scripts/fetch_rcem.py --import-seed
    python scripts/calculate_prosumer_deposit.py --start 2026-05-01 --end 2026-05-31
"""

import argparse
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.financial.prosumer_deposit import (
    calculate_cumulative_deposit,
    calculate_cumulative_deposit_rcem,
    calculate_prosumer_deposit,
    calculate_prosumer_deposit_rcem,
)

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')


def _invoice_deposits(db_path: str, period_start: str):
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        'SELECT pdf_path FROM tauron_bills WHERE billing_period_start = ?',
        (period_start,),
    ).fetchone()
    conn.close()
    if not row or not row[0]:
        return None, None

    meta = row[0]
    prev = re.search(r'depozyt_poprzednie=([\d.]+)', meta)
    period = re.search(r'depozyt_okres=([\d.]+)', meta)
    return (
        float(prev.group(1)) if prev else None,
        float(period.group(1)) if period else None,
    )


def _period_month(start: str) -> str:
    return start[:7]


def _print_rcem_section(summary, dep_prev, dep_period, netting: str):
    print(f'\n{"=" * 70}')
    print(f'RCEm miesięczna (PSE / Tauron): {summary.period_month}  [{netting}]')
    print('=' * 70)
    print(f'   Źródło kWh: {summary.data_source}')
    print(f'   Import: {summary.import_kwh:.1f} kWh | Eksport: {summary.export_kwh:.1f} kWh | Netto: {summary.net_export_kwh:.1f} kWh')
    print(f'   RCEm: {summary.rcem_pln_mwh:.2f} zł/MWh ({summary.rcem_pln_kwh:.5f} zł/kWh) [{summary.rcem_source}]')
    print(f'   Wartość eksportu (brutto): {summary.gross_export_value_pln:.2f} zł')
    label = 'eksport × RCEm' if netting == 'gross' else 'max(0, exp−imp) × RCEm'
    print(f'   Depozyt ({label}): {summary.net_deposit_accrual_pln:.2f} zł')
    if dep_prev is not None:
        diff = summary.net_deposit_accrual_pln - dep_prev
        print(f'\n   Faktura depozyt poprzednie: {dep_prev:.2f} zł  (różnica vs {label}: {diff:+.2f} zł)')
        if summary.rcem_pln_kwh > 0:
            print(f'   Implikowane kWh za {dep_prev:.2f} zł: ~{summary.implied_kwh_for_deposit:.0f} kWh')
    if dep_period is not None:
        print(f'   Faktura depozyt w okresie:  {dep_period:.2f} zł')
    print(f'   Opóźnienie {summary.deposit_delay_months} mc → eksport z okresu {summary.export_month_for_delay}')


def main():
    parser = argparse.ArgumentParser(description='Kalkulator depozytu: RCE godzinowa + RCEm miesięczna')
    parser.add_argument('--start', default='2026-05-01')
    parser.add_argument('--end', default='2026-05-31')
    parser.add_argument('--db', default=DB_PATH)
    parser.add_argument('--source', default='auto', choices=['auto', 'foxess', 'meter'])
    parser.add_argument('--cumulative-from', default=None)
    parser.add_argument('--delay-months', type=int, default=2, help='Opóźnienie depozytu (Tauron, domyślnie 2 mc)')
    parser.add_argument('--rcem-only', action='store_true', help='Tylko RCEm, bez RCE godzinowej')
    parser.add_argument('--rce-only', action='store_true', help='Tylko RCE godzinowa')
    args = parser.parse_args()

    month = _period_month(args.start)
    dep_prev, dep_period = _invoice_deposits(args.db, args.start)

    if not args.rcem_only:
        print('=' * 70)
        print(f'RCE godzinowa (PSE kwadransy): {args.start} – {args.end}')
        print('=' * 70)

        try:
            summary, hourly = calculate_prosumer_deposit(
                args.db, args.start, args.end,
                exchange_source=args.source,
                invoice_deposit_previous=dep_prev,
                invoice_deposit_period=dep_period,
            )
            print(f'\n📊 Źródło wymiany: {summary.data_source}')
            print(f'   Import: {summary.total_import_kwh:.1f} kWh | Eksport: {summary.total_export_kwh:.1f} kWh')
            print(f'   Wartość eksportu (brutto): {summary.gross_export_value_pln:.2f} zł')
            print(f'   Śr. RCE przy eksporcie: {summary.avg_rce_when_exporting:.4f} zł/kWh')
            print(f'   Depozyt godzinowy net: {summary.net_deposit_accrual_pln:.2f} zł')

            if dep_prev is not None:
                print(f'   Faktura depozyt poprzednie: {dep_prev:.2f} zł (różnica: {summary.net_deposit_accrual_pln - dep_prev:+.2f} zł)')

            if args.cumulative_from:
                cum = calculate_cumulative_deposit(args.db, args.cumulative_from, args.end, args.source)
                print(f'\n   Narastająco RCE godz. {args.cumulative_from}–{args.end}: {cum:.2f} zł')
        except ValueError as e:
            print(f'⚠️  RCE godzinowa: {e}')

    if not args.rce_only:
        for netting in ('gross', 'net'):
            try:
                rcem = calculate_prosumer_deposit_rcem(
                    args.db, month,
                    exchange_source=args.source,
                    netting=netting,
                    invoice_deposit_previous=dep_prev,
                    invoice_deposit_period=dep_period,
                    deposit_delay_months=args.delay_months,
                )
                _print_rcem_section(rcem, dep_prev, dep_period, netting)
            except ValueError as e:
                print(f'\n⚠️  RCEm ({netting}): {e}')
                if netting == 'gross':
                    print('   Uruchom: python scripts/fetch_rcem.py --import-seed')

        if args.cumulative_from:
            cum_from = _period_month(args.cumulative_from)
            df = calculate_cumulative_deposit_rcem(args.db, cum_from, month, args.source, netting='gross')
            if not df.empty:
                total = df['net_deposit_accrual_pln'].sum()
                print(f'\n📈 RCEm narastająco ({cum_from}–{month}): {total:.2f} zł')
                print(df[['period_month', 'export_kwh', 'rcem_pln_mwh', 'net_deposit_accrual_pln']].to_string(index=False))


if __name__ == '__main__':
    main()
