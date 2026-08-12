"""
Faktura VAT KOREKTA T/K1/BC486389/0009/25 → do T/K1/0481598/25 (20/05/2025)
Okres: 28/03/2025–24/04/2025 | G12W | moc 14 kW

Uruchomienie:
    python scripts/add_tauron_korekta_2025_03.py
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.data.import_csv import EnergyDataImporter
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')

# Odczyt zdalny 24/04/2025 — po bilansowaniu godzinowym Tauron
KWH_SZCZYT_POBIOR = 108.0
KWH_POZASZCZYT_POBIOR = 225.0
KWH_TOTAL_POBIOR = 333.0
KWH_EXPORT_SZCZYT = 2.0
KWH_EXPORT_POZASZCZYT = 2.0
KWH_EXPORT_TOTAL = 4.0

BILL_SUMMARY = {
    'wartosc_netto_zl': 273.34,
    'vat_zl': 62.84,
    'wartosc_brutto_zl': 336.18,
    'pobor_kwh': 333.0,
    'wprowadzone_do_sieci_kwh': 4.0,
    'srednia_cena_brutto_zl_kwh': 1.01,  # z faktury; 336,18/333 ≈ 1,0095
}

TAURON_TARIFF_KOREKTA = {
    'valid_from': '2025-03-28',
    'tariff_name': 'G12w',
    'price_zone1_day': 0.50500,
    'price_zone2_night': 0.50500,
    'distribution_zone1': 0.32710 + 0.03210,
    'distribution_zone2': 0.05180 + 0.03210,
    'oze_fee_kwh': 0.00350,
    'cogenerative_fee_kwh': 0.00300,
    'subscription_fee_monthly': 17.48 + 0.38,
    'power_fee_monthly': 0.0,
    'notes': (
        'Korekta T/K1/BC486389/0009/25 (wyst. 31/12/2025) → fv T/K1/0481598/25. '
        'Przyczyna: depozyt/RCE. Cennik: EE_GD MIX Eko_NowaEnergiaMix TS_9_Q1_01.03.25-28.02.34. '
        'G12W, 14 kW. Energia 0,505 zł/kWh netto szczyt=pozaszczyt. '
        f'Pobór {BILL_SUMMARY["pobor_kwh"]:.0f} kWh, '
        f'oddanie {BILL_SUMMARY["wprowadzone_do_sieci_kwh"]:.0f} kWh, '
        f'śr. cena brutto {BILL_SUMMARY["srednia_cena_brutto_zl_kwh"]:.2f} zł/kWh '
        f'(łącznie energia+dystrybucja).'
    ),
}

TAURON_BILL_KOREKTA = {
    'bill_date': '2025-12-31',
    'billing_period_start': '2025-03-28',
    'billing_period_end': '2025-04-24',
    'actual_zone1_kwh': KWH_SZCZYT_POBIOR,
    'actual_zone2_kwh': KWH_POZASZCZYT_POBIOR,
    'actual_total_kwh': KWH_TOTAL_POBIOR,
    'actual_energy_cost': 203.14,
    'actual_distribution_cost': 70.20,
    'actual_fixed_costs': 1.69,  # akcyza (od 335 kWh na fv)
    'actual_total_cost': 336.18,
    'energy_exported_kwh': KWH_EXPORT_TOTAL,
    'energy_exported_value': None,
    'bill_number': 'T/K1/BC486389/0009/25',
    'pdf_path': (
        f'srednia_brutto={BILL_SUMMARY["srednia_cena_brutto_zl_kwh"]}zl_kWh; '
        'korekta_do_T/K1/0481598/25; '
        'prognoza_operatora; fizyczny_start_poboru_21.04.2025; nie_porownywac_z_licznikiem'
    ),
}


def _replace_prior_korekta(conn: sqlite3.Connection) -> None:
    conn.execute(
        "DELETE FROM tauron_bills WHERE bill_number IN (?, ?)",
        ('T/K1/BC486389/0009/25', 'korekta_2025-03-28_2025-04-24'),
    )
    conn.execute(
        "DELETE FROM tauron_bills WHERE billing_period_start = ? AND billing_period_end = ?",
        ('2025-03-28', '2025-04-24'),
    )
    conn.execute(
        "DELETE FROM tauron_tariff WHERE valid_from = ? AND tariff_name = 'G12w'",
        ('2025-03-28',),
    )
    conn.commit()


def main():
    importer = EnergyDataImporter()
    conn = sqlite3.connect(DB_PATH)
    _replace_prior_korekta(conn)
    conn.close()

    print('=' * 70)
    print('Faktura korygująca T/K1/BC486389/0009/25')
    print('Okres 28/03/2025 – 24/04/2025 | G12W | 14 kW')
    print('=' * 70)

    print('\n1️⃣  Cennik (stawki jednostkowe z załącznika)...')
    importer.import_tauron_tariff(data_dict=TAURON_TARIFF_KOREKTA)
    print('   ✅ tauron_tariff')

    print('\n2️⃣  Rachunek rozliczeniowy (tauron_bills)...')
    importer.import_tauron_bill(data_dict=TAURON_BILL_KOREKTA)
    print('   ✅ tauron_bills')

    print('\n📋 Zestawienie z faktury:')
    z = BILL_SUMMARY
    print(f'   Pobór {z["pobor_kwh"]:.0f} kWh, oddanie {z["wprowadzone_do_sieci_kwh"]:.0f} kWh')
    print(f'   Netto {z["wartosc_netto_zl"]:.2f} | VAT {z["vat_zl"]:.2f} | Brutto {z["wartosc_brutto_zl"]:.2f} zł')
    print(f'   Średnia cena brutto 1 kWh: {z["srednia_cena_brutto_zl_kwh"]:.2f} zł/kWh '
          f'(sprawdzenie: {z["wartosc_brutto_zl"]/z["pobor_kwh"]:.3f})')

    print('\n📋 Podsumowanie z faktury (POLICZONO = NALEŻAŁO, do zapłaty 0 zł):')
    print(f'   Pobór:     {KWH_TOTAL_POBIOR:.0f} kWh '
          f'(szczyt {KWH_SZCZYT_POBIOR:.0f} + pozaszczyt {KWH_POZASZCZYT_POBIOR:.0f})')
    print(f'   Oddanie:   {KWH_EXPORT_TOTAL:.0f} kWh do sieci')
    print(f'   Netto:     273,34 zł  |  VAT: 62,84 zł  |  Brutto: 336,18 zł')
    print(f'   Energia:   203,14 netto / 249,85 brutto')
    print(f'   Dystryb.:  70,20 netto / 86,33 brutto')
    print(f'   Akcyza:    1,69 zł')
    print(f'   Depozyt prosumenta: 0,00 zł (prognoza depozytu 0)')

    print('\n📌 vs blankiet prognozy T/K1/0411004/25/1:')
    print('   Prognoza: 566 kWh, brutto 568,69 zł (28/03–30/04, okres szerszy)')
    print('   Korekta:  333 kWh, brutto 336,18 zł (28/03–24/04)')

    summary = importer.get_data_summary()
    print(f"\n   W bazie: tauron_tariff={summary.get('tauron_tariff', 0)}, "
          f"tauron_bills={summary.get('tauron_bills', 0)}, "
          f"tauron_forecast={summary.get('tauron_forecast', 0)}")
    importer.close()


if __name__ == '__main__':
    main()
