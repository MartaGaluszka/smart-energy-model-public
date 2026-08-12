"""
Raport: depozyt prosumencki — RCEm (należne) vs faktury Tauron (użyte).

Okres PV: od pierwszego rozliczenia z oddaniem energii (kwiecień/maj 2025).

Uruchomienie:
    python scripts/fetch_rcem.py --import-seed
    python scripts/analysis/report_deposit_rcem.py
    python scripts/analysis/report_deposit_rcem.py --csv data/processed/raport_depozyt_rcem.csv
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.financial.prosumer_deposit import load_deposit_rcem_report

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')


def print_report(report: dict) -> None:
    accrual = report['accrual']
    invoices = report['invoices']
    summary = report['summary']

    print('=' * 78)
    print('RAPORT DEPOZYT PROSUMENCKI — RCEm vs Tauron')
    print(f'Opóźnienie depozytu: {summary["delay_months"]} mc')
    print('=' * 78)

    print('\n## 1. Należny depozyt za każdy miesiąc eksportu (oddanie × RCEm)\n')
    cols = ['miesiac_eksportu', 'oddanie_kwh', 'rcem_zl_mwh', 'nalezny_depozyt_zl', 'faktura_docelowa']
    print(accrual[cols].to_string(index=False))
    print(f'\n   SUMA należnego depozytu: {summary["suma_nalezny_rcem_zl"]:.2f} zł')

    print('\n## 2. Depozyt użyty na fakturach (poz. 5)\n')
    cols2 = [
        'faktura_za_miesiac', 'depozyt_uzyty_faktura_zl', 'nalezne_rcem_2mc_zl',
        'roznica_uzyty_minus_nalezne', 'saldo_model_po_zl', 'eksport_rozliczany_z_miesiecy',
    ]
    print(invoices[cols2].to_string(index=False))
    print(f'\n   SUMA depozytu użytego: {summary["suma_uzyty_faktury_zl"]:.2f} zł')

    print('\n## 3. Podsumowanie\n')
    print(f'   Należne wg RCEm:  {summary["suma_nalezny_rcem_zl"]:>10.2f} zł')
    print(f'   Użyte na fakturach: {summary["suma_uzyty_faktury_zl"]:>10.2f} zł')
    print(f'   Saldo modelu (koniec): {summary["saldo_model_koncowe_zl"]:>8.2f} zł')


def main():
    parser = argparse.ArgumentParser(description='Raport depozyt RCEm vs Tauron')
    parser.add_argument('--db', default=DB_PATH)
    parser.add_argument('--csv', default=None, help='Zapisz tabele do CSV')
    parser.add_argument('--delay', type=int, default=2)
    args = parser.parse_args()

    report = load_deposit_rcem_report(args.db, delay_months=args.delay)
    print_report(report)

    if args.csv:
        os.makedirs(os.path.dirname(args.csv) or '.', exist_ok=True)
        report['accrual'].to_csv(args.csv.replace('.csv', '_eksport.csv'), index=False)
        report['invoices'].to_csv(args.csv.replace('.csv', '_faktury.csv'), index=False)
        print(f'\n💾 Zapisano: {args.csv.replace(".csv", "_eksport.csv")}')


if __name__ == '__main__':
    main()
