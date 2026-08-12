"""
Rozliczenie Tauron — październik 2025 (01/10/2025–31/10/2025).

Uruchomienie:
    source venv/bin/activate
    python scripts/add_tauron_rozliczenie_2025_10.py
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
    'tytul': 'Rozliczenie 10.2025',
    'okres': '01/10/2025 - 31/10/2025',
    'grupa_taryfowa': 'G12W',
    'moc_umowna_kw': 14,
    'nazwa_cennika': 'EE_GD MIX Eko_NowaEnergiaMix TS_9_Q1_01.03.25-28.02.34',
}

# Rozliczenie ilości kWh: faktura 186, prognoza 0, rozliczenie prognoz +186
KWH_POBIOR_SZCZYT = 87.0
KWH_POBIOR_POZASZCZYT = 99.0
KWH_POBIOR_TOTAL = 186.0
KWH_ODDANIE_TOTAL = 77.0

BILL_SUMMARY = {
    'wartosc_netto_zl': 176.61,
    'vat_zl': 40.63,
    'wartosc_brutto_zl': 217.24,
    'srednia_cena_brutto_zl_kwh': 1.17,
    'energia_netto_zl': 113.98,
    'energia_brutto_zl': 140.20,
    'dystrybucja_netto_zl': 62.63,
    'dystrybucja_brutto_zl': 77.04,
}

TAURON_TARIFF = {
    'valid_from': '2025-10-01',
    'tariff_name': 'G12w',
    'price_zone1_day': 0.50500,
    'price_zone2_night': 0.50500,
    'distribution_zone1': 0.32710 + 0.03210,
    'distribution_zone2': 0.05180 + 0.03210,
    'oze_fee_kwh': 0.00350,
    'cogenerative_fee_kwh': 0.00300,
    'subscription_fee_monthly': 20.041 + 4.56,
    'power_fee_monthly': 6.86,
    'notes': (
        f'{ROZLICZENIE_HEADER["tytul"]} | {ROZLICZENIE_HEADER["okres"]}. '
        f'{ROZLICZENIE_HEADER["grupa_taryfowa"]}, moc {ROZLICZENIE_HEADER["moc_umowna_kw"]} kW. '
        f'Cennik: {ROZLICZENIE_HEADER["nazwa_cennika"]}. '
        'Energia 0,505 zł/kWh netto (szczyt=pozaszczyt, promocja). '
        'Opłata handlowa 20,04 zł, opłata przejściowa 0,10 zł, opłata mocowa 6,86 zł netto. '
        f'Pobór {KWH_POBIOR_TOTAL:.0f} kWh (szczyt {KWH_POBIOR_SZCZYT:.0f} + '
        f'pozaszczyt {KWH_POBIOR_POZASZCZYT:.0f}), oddanie {KWH_ODDANIE_TOTAL:.0f} kWh. '
        f'Śr. brutto {BILL_SUMMARY["srednia_cena_brutto_zl_kwh"]:.2f} zł/kWh. '
        'Prognoza 0 kWh, rozliczenie 186 kWh.'
    ),
}

TAURON_BILL = {
    'bill_date': '2025-10-31',
    'billing_period_start': '2025-10-01',
    'billing_period_end': '2025-10-31',
    'actual_zone1_kwh': KWH_POBIOR_SZCZYT,
    'actual_zone2_kwh': KWH_POBIOR_POZASZCZYT,
    'actual_total_kwh': KWH_POBIOR_TOTAL,
    'actual_energy_cost': BILL_SUMMARY['energia_netto_zl'],
    'actual_distribution_cost': BILL_SUMMARY['dystrybucja_netto_zl'],
    'actual_fixed_costs': 0.0,
    'actual_total_cost': BILL_SUMMARY['wartosc_brutto_zl'],
    'energy_exported_kwh': KWH_ODDANIE_TOTAL,
    'energy_exported_value': None,
    'bill_number': 'rozliczenie_10.2025_2025-10-01_31',
    'pdf_path': f'{ROZLICZENIE_HEADER["tytul"]}|G12W|14kW|cennik=EE_GD_MIX_Eko_NowaEnergiaMix',
}


def _replace_prior(conn: sqlite3.Connection) -> None:
    conn.execute(
        'DELETE FROM tauron_bills WHERE bill_number = ?',
        (TAURON_BILL['bill_number'],),
    )
    conn.execute(
        "DELETE FROM tauron_tariff WHERE valid_from = ? AND notes LIKE '%Rozliczenie 10.2025%'",
        ('2025-10-01',),
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
    print(f'   Oddanie: {KWH_ODDANIE_TOTAL:.0f} kWh')
    print(f'   Energia netto {z["energia_netto_zl"]:.2f} / brutto {z["energia_brutto_zl"]:.2f} zł')
    print(f'   Dystryb. netto {z["dystrybucja_netto_zl"]:.2f} / brutto {z["dystrybucja_brutto_zl"]:.2f} zł')
    print(f'   Razem brutto {z["wartosc_brutto_zl"]:.2f} zł | Śr. {z["srednia_cena_brutto_zl_kwh"]:.2f} zł/kWh')

    print('\n   Rozliczenie prognoz: faktura 186 kWh, prognoza 0 kWh → +186 kWh')

    print('\n📌 vs blankiet prognozy T/K1/0411004/25/4 (09–10/2025):')
    print('   Blankiet (2 mies.): 1016 kWh, brutto 1073,15 zł')
    print('   IX + X rzeczywiste: 77 + 186 = 263 kWh pobór, 111,97 + 217,24 = 329,21 zł brutto')

    summary = importer.get_data_summary()
    print(f"\n   tauron_bills: {summary.get('tauron_bills', 0)} rekordów")
    importer.close()


if __name__ == '__main__':
    main()
