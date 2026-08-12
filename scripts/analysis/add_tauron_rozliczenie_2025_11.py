"""
Rozliczenie Tauron — listopad 2025 (01/11/2025–30/11/2025).

Odczyt licznika 30/11/2025 (Z): pobór szczyt 177 + pozaszczyt 390 kWh; oddanie 17 + 39 kWh.

Uruchomienie:
    source venv/bin/activate
    python scripts/add_tauron_rozliczenie_2025_11.py
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

ROZLICZENIE_HEADER = {
    'tytul': 'Rozliczenie 11.2025',
    'okres': '01/11/2025 - 30/11/2025',
    'grupa_taryfowa': 'G12W',
    'moc_umowna_kw': 14,
    'nazwa_cennika': 'EE_GD MIX Eko_NowaEnergiaMix TS_9_Q1_01.03.25-28.02.34',
}

# Odczyt zdalny 30/11/2025 (Z) — ilości zgodne z pozycjami na fakturze
KWH_POBIOR_SZCZYT = 177.0
KWH_POBIOR_POZASZCZYT = 390.0
KWH_POBIOR_TOTAL = 567.0
KWH_ODDANIE_SZCZYT = 17.0
KWH_ODDANIE_POZASZCZYT = 39.0
KWH_ODDANIE_TOTAL = 56.0

BILL_SUMMARY = {
    'wartosc_netto_zl': 433.04,
    'vat_zl': 99.62,
    'wartosc_brutto_zl': 532.66,
    'srednia_cena_brutto_zl_kwh': round(532.66 / KWH_POBIOR_TOTAL, 2),
    'energia_netto_zl': 306.38,
    'energia_brutto_zl': 376.85,
    'dystrybucja_netto_zl': 126.66,
    'dystrybucja_brutto_zl': 155.81,
}

TAURON_TARIFF = {
    'valid_from': '2025-11-01',
    'tariff_name': 'G12w',
    'price_zone1_day': 0.50500,
    'price_zone2_night': 0.50500,
    'distribution_zone1': 0.32710 + 0.03210,
    'distribution_zone2': 0.05180 + 0.03210,
    'oze_fee_kwh': 0.00350,
    'cogenerative_fee_kwh': 0.00300,
    'subscription_fee_monthly': 20.041 + 4.56,
    'power_fee_monthly': 11.44,
    'notes': (
        f'{ROZLICZENIE_HEADER["tytul"]} | {ROZLICZENIE_HEADER["okres"]}. '
        f'{ROZLICZENIE_HEADER["grupa_taryfowa"]}, moc {ROZLICZENIE_HEADER["moc_umowna_kw"]} kW. '
        f'Cennik: {ROZLICZENIE_HEADER["nazwa_cennika"]}. '
        'Energia 0,505 zł/kWh netto (szczyt=pozaszczyt, promocja). '
        'Opłata handlowa 20,04 zł, opłata przejściowa 0,33 zł, opłata mocowa 11,44 zł netto. '
        f'Odczyt 30/11/2025 (Z). Pobór {KWH_POBIOR_TOTAL:.0f} kWh (szczyt {KWH_POBIOR_SZCZYT:.0f} + '
        f'pozaszczyt {KWH_POBIOR_POZASZCZYT:.0f}), oddanie {KWH_ODDANIE_TOTAL:.0f} kWh '
        f'(szczyt {KWH_ODDANIE_SZCZYT:.0f} + pozaszczyt {KWH_ODDANIE_POZASZCZYT:.0f}). '
        f'Śr. brutto {BILL_SUMMARY["srednia_cena_brutto_zl_kwh"]:.2f} zł/kWh.'
    ),
}

TAURON_BILL = {
    'bill_date': '2025-11-30',
    'billing_period_start': '2025-11-01',
    'billing_period_end': '2025-11-30',
    'actual_zone1_kwh': KWH_POBIOR_SZCZYT,
    'actual_zone2_kwh': KWH_POBIOR_POZASZCZYT,
    'actual_total_kwh': KWH_POBIOR_TOTAL,
    'actual_energy_cost': BILL_SUMMARY['energia_netto_zl'],
    'actual_distribution_cost': BILL_SUMMARY['dystrybucja_netto_zl'],
    'actual_fixed_costs': 0.0,
    'actual_total_cost': BILL_SUMMARY['wartosc_brutto_zl'],
    'energy_exported_kwh': KWH_ODDANIE_TOTAL,
    'energy_exported_value': None,
    'bill_number': 'rozliczenie_11.2025_2025-11-01_30',
    'pdf_path': f'{ROZLICZENIE_HEADER["tytul"]}|G12W|14kW|cennik=EE_GD_MIX_Eko_NowaEnergiaMix',
}


def _replace_prior(conn: sqlite3.Connection) -> None:
    conn.execute(
        'DELETE FROM tauron_bills WHERE bill_number = ?',
        (TAURON_BILL['bill_number'],),
    )
    conn.execute(
        "DELETE FROM tauron_tariff WHERE valid_from = ? AND notes LIKE '%Rozliczenie 11.2025%'",
        ('2025-11-01',),
    )
    conn.commit()


def main():
    conn = sqlite3.connect(DB_PATH)
    _replace_prior(conn)
    conn.close()

    importer = EnergyDataImporter()
    h = ROZLICZENIE_HEADER
    z = BILL_SUMMARY

    print('=' * 70)
    print(h['tytul'])
    print(f'{h["okres"]} | {h["grupa_taryfowa"]} | moc {h["moc_umowna_kw"]} kW')
    print(f'Cennik: {h["nazwa_cennika"]}')
    print('=' * 70)

    importer.import_tauron_tariff(data_dict=TAURON_TARIFF)
    print('✅ tauron_tariff')

    importer.import_tauron_bill(data_dict=TAURON_BILL)
    print('✅ tauron_bills')

    print(f'\n   Pobór:   {KWH_POBIOR_TOTAL:.0f} kWh '
          f'(szczyt {KWH_POBIOR_SZCZYT:.0f} + pozaszczyt {KWH_POBIOR_POZASZCZYT:.0f})')
    print(f'   Oddanie: {KWH_ODDANIE_TOTAL:.0f} kWh '
          f'(szczyt {KWH_ODDANIE_SZCZYT:.0f} + pozaszczyt {KWH_ODDANIE_POZASZCZYT:.0f})')
    print(f'   Energia netto {z["energia_netto_zl"]:.2f} / brutto {z["energia_brutto_zl"]:.2f} zł')
    print(f'   Dystryb. netto {z["dystrybucja_netto_zl"]:.2f} / brutto {z["dystrybucja_brutto_zl"]:.2f} zł')
    print(f'   Razem brutto {z["wartosc_brutto_zl"]:.2f} zł | Śr. {z["srednia_cena_brutto_zl_kwh"]:.2f} zł/kWh')

    print('\n📌 vs blankiet prognozy T/K1/0411004/25/5 (11–12/2025):')
    print('   Blankiet (2 mies.): 1016 kWh, brutto 1151,43 zł')
    print(f'   Listopad 2025:      {KWH_POBIOR_TOTAL:.0f} kWh pobór, brutto {z["wartosc_brutto_zl"]:.2f} zł')

    summary = importer.get_data_summary()
    print(f"\n   tauron_bills: {summary.get('tauron_bills', 0)} rekordów")
    importer.close()


if __name__ == '__main__':
    main()
