"""
Rozliczenie Tauron — grudzień 2025 (01/12/2025–31/12/2025).

Odczyt licznika 31/12/2025 (Z): pobór szczyt 309 + pozaszczyt 539 kWh; oddanie 0 + 0 kWh.

Uruchomienie:
    source venv/bin/activate
    python scripts/add_tauron_rozliczenie_2025_12.py
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
    'tytul': 'Rozliczenie 12.2025',
    'okres': '01/12/2025 - 31/12/2025',
    'grupa_taryfowa': 'G12W',
    'moc_umowna_kw': 14,
    'nazwa_cennika': 'EE_GD MIX Eko_NowaEnergiaMix TS_9_Q1_01.03.25-28.02.34',
    'termin_platnosci': '2026-02-05',
}

# Odczyt zdalny 31/12/2025 (Z) — ilości zgodne z pozycjami na fakturze
KWH_POBIOR_SZCZYT = 309.0
KWH_POBIOR_POZASZCZYT = 539.0
KWH_POBIOR_TOTAL = 848.0
KWH_ODDANIE_SZCZYT = 0.0
KWH_ODDANIE_POZASZCZYT = 0.0
KWH_ODDANIE_TOTAL = 0.0

BILL_SUMMARY = {
    'wartosc_netto_zl': 636.69,
    'vat_zl': 146.44,
    'wartosc_brutto_zl': 783.13,
    'srednia_cena_brutto_zl_kwh': round(783.13 / KWH_POBIOR_TOTAL, 2),
    'energia_netto_zl': 448.29,
    'energia_brutto_zl': 551.40,
    'dystrybucja_netto_zl': 188.40,
    'dystrybucja_brutto_zl': 231.73,
    'depozyt_poprzednie': 91.95,
    'do_zaplaty_po_depozycie': 691.18,
}

TAURON_TARIFF = {
    'valid_from': '2025-12-01',
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
        f'Odczyt 31/12/2025 (Z). Pobór {KWH_POBIOR_TOTAL:.0f} kWh (szczyt {KWH_POBIOR_SZCZYT:.0f} + '
        f'pozaszczyt {KWH_POBIOR_POZASZCZYT:.0f}), oddanie {KWH_ODDANIE_TOTAL:.0f} kWh. '
        f'Depozyt poprzednie {BILL_SUMMARY["depozyt_poprzednie"]:.2f} zł, '
        f'do zapłaty {BILL_SUMMARY["do_zaplaty_po_depozycie"]:.2f} zł. '
        f'Śr. brutto {BILL_SUMMARY["srednia_cena_brutto_zl_kwh"]:.2f} zł/kWh.'
    ),
}

TAURON_BILL = {
    'bill_date': '2025-12-31',
    'billing_period_start': '2025-12-01',
    'billing_period_end': '2025-12-31',
    'actual_zone1_kwh': KWH_POBIOR_SZCZYT,
    'actual_zone2_kwh': KWH_POBIOR_POZASZCZYT,
    'actual_total_kwh': KWH_POBIOR_TOTAL,
    'actual_energy_cost': BILL_SUMMARY['energia_netto_zl'],
    'actual_distribution_cost': BILL_SUMMARY['dystrybucja_netto_zl'],
    'actual_fixed_costs': 0.0,
    'actual_total_cost': BILL_SUMMARY['wartosc_brutto_zl'],
    'energy_exported_kwh': KWH_ODDANIE_TOTAL,
    'energy_exported_value': None,
    'bill_number': 'rozliczenie_12.2025_2025-12-01_31',
    'pdf_path': (
        f'{ROZLICZENIE_HEADER["tytul"]}|G12W|14kW|cennik=EE_GD_MIX_Eko_NowaEnergiaMix|'
        f'depozyt_poprzednie={BILL_SUMMARY["depozyt_poprzednie"]}|'
        f'do_zaplaty_po_depozycie={BILL_SUMMARY["do_zaplaty_po_depozycie"]}|'
        f'termin_platnosci={ROZLICZENIE_HEADER["termin_platnosci"]}'
    ),
}


def _replace_prior(conn: sqlite3.Connection) -> None:
    conn.execute(
        'DELETE FROM tauron_bills WHERE bill_number = ?',
        (TAURON_BILL['bill_number'],),
    )
    conn.execute(
        "DELETE FROM tauron_tariff WHERE valid_from = ? AND notes LIKE '%Rozliczenie 12.2025%'",
        ('2025-12-01',),
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
    print(f'   Depozyt poprzednie {z["depozyt_poprzednie"]:.2f} zł → do zapłaty {z["do_zaplaty_po_depozycie"]:.2f} zł')
    print(f'   Termin płatności: {h["termin_platnosci"]}')

    print('\n📌 vs blankiet prognozy T/K1/0411004/25/5 (11–12/2025):')
    print('   Blankiet (2 mies.): 1016 kWh, brutto 1151,43 zł')
    print(f'   Listopad 2025:       567 kWh pobór, brutto 532,66 zł')
    print(f'   Grudzień 2025:       {KWH_POBIOR_TOTAL:.0f} kWh pobór, brutto {z["wartosc_brutto_zl"]:.2f} zł')
    print(f'   XI+XII łącznie:      {567 + KWH_POBIOR_TOTAL:.0f} kWh, brutto {532.66 + z["wartosc_brutto_zl"]:.2f} zł')

    summary = importer.get_data_summary()
    print(f"\n   tauron_bills: {summary.get('tauron_bills', 0)} rekordów")
    importer.close()


if __name__ == '__main__':
    main()
