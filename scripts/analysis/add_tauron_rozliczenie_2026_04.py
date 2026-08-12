"""
Rozliczenie Tauron — kwiecień 2026 (01/04/2026–30/04/2026).

Odczyt licznika 30/04/2026 (Z): pobór szczyt 41 + pozaszczyt 93 kWh; oddanie 121 + 167 kWh.

Uruchomienie:
    source venv/bin/activate
    python scripts/add_tauron_rozliczenie_2026_04.py
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
    'tytul': 'Rozliczenie 04.2026',
    'okres': '01/04/2026 - 30/04/2026',
    'grupa_taryfowa': 'G12W',
    'moc_umowna_kw': 14,
    'nazwa_cennika': 'EE_GD MIX Eko_NowaEnergiaMix TS_9_Q1_01.03.25-28.02.34',
    'termin_platnosci': '2026-05-28',
}

KWH_POBIOR_SZCZYT = 41.0
KWH_POBIOR_POZASZCZYT = 93.0
KWH_POBIOR_TOTAL = 134.0
KWH_ODDANIE_SZCZYT = 121.0
KWH_ODDANIE_POZASZCZYT = 167.0
KWH_ODDANIE_TOTAL = 288.0

BILL_SUMMARY = {
    'wartosc_netto_zl': 153.51,
    'vat_zl': 35.31,
    'wartosc_brutto_zl': 188.82,
    'srednia_cena_brutto_zl_kwh': 1.41,
    'energia_netto_zl': 89.93,
    'energia_brutto_zl': 110.62,
    'dystrybucja_netto_zl': 63.58,
    'dystrybucja_brutto_zl': 78.20,
    'akcyza_zl': 1.07,
    'depozyt_okres': 0.0,
    'depozyt_poprzednie': 38.67,
    'do_zaplaty_po_depozycie': 150.15,
}

TAURON_TARIFF = {
    'valid_from': '2026-04-01',
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
        'Energia szczyt 0,6244 / pozaszczyt 0,4163 zł/kWh netto. '
        f'Odczyt 30/04/2026 (Z). Pobór {KWH_POBIOR_TOTAL:.0f} kWh (szczyt {KWH_POBIOR_SZCZYT:.0f} + '
        f'pozaszczyt {KWH_POBIOR_POZASZCZYT:.0f}), oddanie {KWH_ODDANIE_TOTAL:.0f} kWh '
        f'(szczyt {KWH_ODDANIE_SZCZYT:.0f} + pozaszczyt {KWH_ODDANIE_POZASZCZYT:.0f}). '
        f'Akcyza {BILL_SUMMARY["akcyza_zl"]:.2f} zł (od 213 kWh). '
        f'Depozyt poprzednie {BILL_SUMMARY["depozyt_poprzednie"]:.2f} zł, '
        f'do zapłaty {BILL_SUMMARY["do_zaplaty_po_depozycie"]:.2f} zł. '
        f'Śr. brutto {BILL_SUMMARY["srednia_cena_brutto_zl_kwh"]:.2f} zł/kWh. '
        'Analogiczny okres rok wcześniej: 287 kWh.'
    ),
}

TAURON_BILL = {
    'bill_date': '2026-04-30',
    'billing_period_start': '2026-04-01',
    'billing_period_end': '2026-04-30',
    'actual_zone1_kwh': KWH_POBIOR_SZCZYT,
    'actual_zone2_kwh': KWH_POBIOR_POZASZCZYT,
    'actual_total_kwh': KWH_POBIOR_TOTAL,
    'actual_energy_cost': BILL_SUMMARY['energia_netto_zl'],
    'actual_distribution_cost': BILL_SUMMARY['dystrybucja_netto_zl'],
    'actual_fixed_costs': BILL_SUMMARY['akcyza_zl'],
    'actual_total_cost': BILL_SUMMARY['wartosc_brutto_zl'],
    'energy_exported_kwh': KWH_ODDANIE_TOTAL,
    'energy_exported_value': None,
    'bill_number': 'rozliczenie_04.2026_2026-04-01_30',
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
        "DELETE FROM tauron_tariff WHERE valid_from = ? AND notes LIKE '%Rozliczenie 04.2026%'",
        ('2026-04-01',),
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

    print('\n📌 Trend 2026 (pobór / oddanie / brutto):')
    print('   Styczeń: 1175 /   8 kWh → 996,70 zł')
    print('   Luty:     743 /  71 kWh → 582,36 zł')
    print(f'   Marzec:   223 / 246 kWh → 254,36 zł')
    print(f'   Kwiecień: {KWH_POBIOR_TOTAL:.0f} / {KWH_ODDANIE_TOTAL:.0f} kWh → {z["wartosc_brutto_zl"]:.2f} zł')

    summary = importer.get_data_summary()
    print(f"\n   tauron_bills: {summary.get('tauron_bills', 0)} rekordów")
    importer.close()


if __name__ == '__main__':
    main()
