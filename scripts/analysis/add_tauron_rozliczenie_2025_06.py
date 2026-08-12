"""
Rozliczenie Tauron — czerwiec 2025 (01/06/2025–30/06/2025).

Uruchomienie:
    source venv/bin/activate
    python scripts/add_tauron_rozliczenie_2025_06.py
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
    'tytul': 'Rozliczenie 06.2025',
    'okres': '01/06/2025 - 30/06/2025',
    'grupa_taryfowa': 'G12W',
    'moc_umowna_kw': 14,
    'nazwa_cennika': 'EE_GD MIX Eko_NowaEnergiaMix TS_9_Q1_01.03.25-28.02.34',
}

# Rozliczenie ilości kWh: faktura 8, prognoza 0, rozliczenie prognoz +8
KWH_POBIOR_SZCZYT = 2.0
KWH_POBIOR_POZASZCZYT = 6.0
KWH_POBIOR_TOTAL = 8.0
KWH_ODDANIE_TOTAL = 671.0

BILL_SUMMARY = {
    'wartosc_netto_zl': 37.71,
    'vat_zl': 8.65,
    'wartosc_brutto_zl': 46.36,
    'srednia_cena_brutto_zl_kwh': 5.79,
    'energia_netto_zl': 21.52,
    'energia_brutto_zl': 26.47,
    'dystrybucja_netto_zl': 16.19,
    'dystrybucja_brutto_zl': 19.89,
}

TAURON_TARIFF = {
    'valid_from': '2025-06-01',
    'tariff_name': 'G12w',
    'price_zone1_day': 0.50500,
    'price_zone2_night': 0.50500,
    'distribution_zone1': 0.32710 + 0.03210,
    'distribution_zone2': 0.05180 + 0.03210,
    'oze_fee_kwh': 0.00350,
    'cogenerative_fee_kwh': 0.00300,
    'subscription_fee_monthly': 17.48 + 4.56,
    'power_fee_monthly': 0.0,
    'notes': (
        f'{ROZLICZENIE_HEADER["tytul"]} | {ROZLICZENIE_HEADER["okres"]}. '
        f'{ROZLICZENIE_HEADER["grupa_taryfowa"]}, moc {ROZLICZENIE_HEADER["moc_umowna_kw"]} kW. '
        f'Cennik: {ROZLICZENIE_HEADER["nazwa_cennika"]}. '
        'Energia 0,505 zł/kWh netto (szczyt=pozaszczyt, promocja). '
        f'Pobór {KWH_POBIOR_TOTAL:.0f} kWh (szczyt {KWH_POBIOR_SZCZYT:.0f} + '
        f'pozaszczyt {KWH_POBIOR_POZASZCZYT:.0f}), oddanie {KWH_ODDANIE_TOTAL:.0f} kWh. '
        f'Śr. brutto {BILL_SUMMARY["srednia_cena_brutto_zl_kwh"]:.2f} zł/kWh. '
        'Prognoza 0 kWh, rozliczenie 8 kWh.'
    ),
}

TAURON_BILL = {
    'bill_date': '2025-06-30',
    'billing_period_start': '2025-06-01',
    'billing_period_end': '2025-06-30',
    'actual_zone1_kwh': KWH_POBIOR_SZCZYT,
    'actual_zone2_kwh': KWH_POBIOR_POZASZCZYT,
    'actual_total_kwh': KWH_POBIOR_TOTAL,
    'actual_energy_cost': BILL_SUMMARY['energia_netto_zl'],
    'actual_distribution_cost': BILL_SUMMARY['dystrybucja_netto_zl'],
    'actual_fixed_costs': 0.0,
    'actual_total_cost': BILL_SUMMARY['wartosc_brutto_zl'],
    'energy_exported_kwh': KWH_ODDANIE_TOTAL,
    'energy_exported_value': None,
    'bill_number': 'rozliczenie_06.2025_2025-06-01_30',
    'pdf_path': f'{ROZLICZENIE_HEADER["tytul"]}|G12W|14kW|cennik=EE_GD_MIX_Eko_NowaEnergiaMix',
}


def _replace_prior(conn: sqlite3.Connection) -> None:
    conn.execute(
        'DELETE FROM tauron_bills WHERE bill_number = ?',
        (TAURON_BILL['bill_number'],),
    )
    conn.execute(
        "DELETE FROM tauron_tariff WHERE valid_from = ? AND notes LIKE '%Rozliczenie 06.2025%'",
        ('2025-06-01',),
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

    print('\n   Rozliczenie prognoz: faktura 8 kWh, prognoza 0 kWh → +8 kWh')

    print('\n📌 vs blankiet prognozy T/K1/0411004/25/2 (05–06/2025):')
    print('   Blankiet (2 mies.): 1016 kWh, brutto 985,51 zł')
    print(f'   Czerwiec 2025:       {KWH_POBIOR_TOTAL:.0f} kWh pobór, brutto {z["wartosc_brutto_zl"]:.2f} zł')
    print('   Maj + czerwiec łącznie z blankietu vs maj(34)+cze(8) = 42 kWh pobór')

    summary = importer.get_data_summary()
    print(f"\n   tauron_bills: {summary.get('tauron_bills', 0)} rekordów")
    importer.close()


if __name__ == '__main__':
    main()
