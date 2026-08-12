"""
Rozliczenie Tauron — marzec 2026 (01/03/2026–31/03/2026).

Nowe stawki energii od 01/03/2026 (szczyt 0,6244 / pozaszczyt 0,4163 zł/kWh netto).
Odczyt licznika 31/03/2026 (Z): pobór szczyt 57 + pozaszczyt 166 kWh; oddanie 104 + 142 kWh.

Uruchomienie:
    source venv/bin/activate
    python scripts/add_tauron_rozliczenie_2026_03.py
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
    'tytul': 'Rozliczenie 03.2026',
    'okres': '01/03/2026 - 31/03/2026',
    'grupa_taryfowa': 'G12W',
    'moc_umowna_kw': 14,
    'nazwa_cennika': 'EE_GD MIX Eko_NowaEnergiaMix TS_9_Q1_01.03.25-28.02.34',
    'termin_platnosci': '2026-04-24',
}

# Odczyt zdalny 31/03/2026 (Z) — ilości zgodne z pozycjami na fakturze
KWH_POBIOR_SZCZYT = 57.0
KWH_POBIOR_POZASZCZYT = 166.0
KWH_POBIOR_TOTAL = 223.0
KWH_ODDANIE_SZCZYT = 104.0
KWH_ODDANIE_POZASZCZYT = 142.0
KWH_ODDANIE_TOTAL = 246.0

BILL_SUMMARY = {
    'wartosc_netto_zl': 206.78,
    'vat_zl': 47.58,
    'wartosc_brutto_zl': 254.36,
    'srednia_cena_brutto_zl_kwh': 1.14,
    'energia_netto_zl': 130.31,
    'energia_brutto_zl': 160.29,
    'dystrybucja_netto_zl': 76.47,
    'dystrybucja_brutto_zl': 94.07,
    'akcyza_zl': 1.47,
    'depozyt_okres': 0.0,
    'depozyt_poprzednie': 25.89,
    'do_zaplaty_po_depozycie': 228.47,
}

TAURON_TARIFF = {
    'valid_from': '2026-03-01',
    'tariff_name': 'G12w',
    'price_zone1_day': 0.62440,
    'price_zone2_night': 0.41630,
    'distribution_zone1': 0.32980 + 0.03320,
    'distribution_zone2': 0.05120 + 0.03320,
    'oze_fee_kwh': 0.00730,
    'cogenerative_fee_kwh': 0.00300,
    'subscription_fee_monthly': 25.61 + 4.56,
    'power_fee_monthly': 24.05,
    'notes': (
        f'{ROZLICZENIE_HEADER["tytul"]} | {ROZLICZENIE_HEADER["okres"]}. '
        f'{ROZLICZENIE_HEADER["grupa_taryfowa"]}, moc {ROZLICZENIE_HEADER["moc_umowna_kw"]} kW. '
        f'Cennik: {ROZLICZENIE_HEADER["nazwa_cennika"]}. '
        'Nowe stawki od 01/03/2026: energia szczyt 0,6244 / pozaszczyt 0,4163 zł/kWh netto. '
        'Opłata handlowa 25,61 zł, przejściowa 0,00 zł, opłata mocowa 24,05 zł netto. '
        f'Odczyt 31/03/2026 (Z). Pobór {KWH_POBIOR_TOTAL:.0f} kWh (szczyt {KWH_POBIOR_SZCZYT:.0f} + '
        f'pozaszczyt {KWH_POBIOR_POZASZCZYT:.0f}), oddanie {KWH_ODDANIE_TOTAL:.0f} kWh '
        f'(szczyt {KWH_ODDANIE_SZCZYT:.0f} + pozaszczyt {KWH_ODDANIE_POZASZCZYT:.0f}). '
        f'Akcyza {BILL_SUMMARY["akcyza_zl"]:.2f} zł (od 292 kWh). '
        f'Depozyt poprzednie {BILL_SUMMARY["depozyt_poprzednie"]:.2f} zł, '
        f'do zapłaty {BILL_SUMMARY["do_zaplaty_po_depozycie"]:.2f} zł. '
        f'Śr. brutto {BILL_SUMMARY["srednia_cena_brutto_zl_kwh"]:.2f} zł/kWh.'
    ),
}

TAURON_BILL = {
    'bill_date': '2026-03-31',
    'billing_period_start': '2026-03-01',
    'billing_period_end': '2026-03-31',
    'actual_zone1_kwh': KWH_POBIOR_SZCZYT,
    'actual_zone2_kwh': KWH_POBIOR_POZASZCZYT,
    'actual_total_kwh': KWH_POBIOR_TOTAL,
    'actual_energy_cost': BILL_SUMMARY['energia_netto_zl'],
    'actual_distribution_cost': BILL_SUMMARY['dystrybucja_netto_zl'],
    'actual_fixed_costs': BILL_SUMMARY['akcyza_zl'],
    'actual_total_cost': BILL_SUMMARY['wartosc_brutto_zl'],
    'energy_exported_kwh': KWH_ODDANIE_TOTAL,
    'energy_exported_value': None,
    'bill_number': 'rozliczenie_03.2026_2026-03-01_31',
    'pdf_path': (
        f'{ROZLICZENIE_HEADER["tytul"]}|G12W|14kW|cennik=EE_GD_MIX_Eko_NowaEnergiaMix|'
        f'stawki_od=2026-03-01|'
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
        "DELETE FROM tauron_tariff WHERE valid_from = ? AND notes LIKE '%Rozliczenie 03.2026%'",
        ('2026-03-01',),
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
    print(f'   Akcyza {z["akcyza_zl"]:.2f} zł')
    print(f'   Depozyt poprzednie {z["depozyt_poprzednie"]:.2f} zł → do zapłaty {z["do_zaplaty_po_depozycie"]:.2f} zł')
    print(f'   Termin płatności: {h["termin_platnosci"]}')

    print('\n📌 Trend zużycia:')
    print('   Styczeń 2026: 1175 kWh pobór, brutto 996,70 zł')
    print(f'   Marzec 2026:   {KWH_POBIOR_TOTAL:.0f} kWh pobór, brutto {z["wartosc_brutto_zl"]:.2f} zł')
    print(f'   Oddanie marzec: {KWH_ODDANIE_TOTAL:.0f} kWh (produkcja PV > pobór)')

    summary = importer.get_data_summary()
    print(f"\n   tauron_bills: {summary.get('tauron_bills', 0)} rekordów")
    importer.close()


if __name__ == '__main__':
    main()
