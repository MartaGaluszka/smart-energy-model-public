"""
Rozliczenie Tauron — styczeń 2026 (01/01/2026–31/01/2026).

Nowe stawki od 01/01/2026 (koniec promocji 0,505 zł/kWh).
Odczyt licznika 31/01/2026 (Z): pobór szczyt 178 + pozaszczyt 997 kWh; oddanie 1 + 7 kWh.

Uruchomienie:
    source venv/bin/activate
    python scripts/add_tauron_rozliczenie_2026_01.py
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
    'tytul': 'Rozliczenie 01.2026',
    'okres': '01/01/2026 - 31/01/2026',
    'grupa_taryfowa': 'G12W',
    'moc_umowna_kw': 14,
    'nazwa_cennika': 'EE_GD MIX Eko_NowaEnergiaMix TS_9_Q1_01.03.25-28.02.34',
    'termin_platnosci': '2026-03-06',
}

# Odczyt zdalny 31/01/2026 (Z) — ilości zgodne z pozycjami na fakturze
KWH_POBIOR_SZCZYT = 178.0
KWH_POBIOR_POZASZCZYT = 997.0
KWH_POBIOR_TOTAL = 1175.0
KWH_ODDANIE_SZCZYT = 1.0
KWH_ODDANIE_POZASZCZYT = 7.0
KWH_ODDANIE_TOTAL = 8.0

BILL_SUMMARY = {
    'wartosc_netto_zl': 810.33,
    'vat_zl': 186.37,
    'wartosc_brutto_zl': 996.70,
    'srednia_cena_brutto_zl_kwh': 0.85,
    'energia_netto_zl': 610.12,
    'energia_brutto_zl': 750.45,
    'dystrybucja_netto_zl': 200.21,
    'dystrybucja_brutto_zl': 246.25,
    'akcyza_zl': 6.20,
    'depozyt_poprzednie': 0.0,
    'do_zaplaty_po_depozycie': 996.70,
}

TAURON_TARIFF = {
    'valid_from': '2026-01-01',
    'tariff_name': 'G12w',
    'price_zone1_day': 0.80470,
    'price_zone2_night': 0.44260,
    'distribution_zone1': 0.32980 + 0.03310,
    'distribution_zone2': 0.05120 + 0.03310,
    'oze_fee_kwh': 0.00730,
    'cogenerative_fee_kwh': 0.00300,
    'subscription_fee_monthly': 25.61 + 4.56,
    'power_fee_monthly': 24.05,
    'notes': (
        f'{ROZLICZENIE_HEADER["tytul"]} | {ROZLICZENIE_HEADER["okres"]}. '
        f'{ROZLICZENIE_HEADER["grupa_taryfowa"]}, moc {ROZLICZENIE_HEADER["moc_umowna_kw"]} kW. '
        f'Cennik: {ROZLICZENIE_HEADER["nazwa_cennika"]}. '
        'Nowe stawki od 01/01/2026: energia szczyt 0,8047 / pozaszczyt 0,4426 zł/kWh netto. '
        'Opłata handlowa 25,61 zł, przejściowa 0,00 zł, opłata mocowa 24,05 zł netto. '
        f'Odczyt 31/01/2026 (Z). Pobór {KWH_POBIOR_TOTAL:.0f} kWh (szczyt {KWH_POBIOR_SZCZYT:.0f} + '
        f'pozaszczyt {KWH_POBIOR_POZASZCZYT:.0f}), oddanie {KWH_ODDANIE_TOTAL:.0f} kWh '
        f'(szczyt {KWH_ODDANIE_SZCZYT:.0f} + pozaszczyt {KWH_ODDANIE_POZASZCZYT:.0f}). '
        f'Akcyza {BILL_SUMMARY["akcyza_zl"]:.2f} zł (od 1240 kWh). '
        f'Śr. brutto {BILL_SUMMARY["srednia_cena_brutto_zl_kwh"]:.2f} zł/kWh.'
    ),
}

TAURON_BILL = {
    'bill_date': '2026-01-31',
    'billing_period_start': '2026-01-01',
    'billing_period_end': '2026-01-31',
    'actual_zone1_kwh': KWH_POBIOR_SZCZYT,
    'actual_zone2_kwh': KWH_POBIOR_POZASZCZYT,
    'actual_total_kwh': KWH_POBIOR_TOTAL,
    'actual_energy_cost': BILL_SUMMARY['energia_netto_zl'],
    'actual_distribution_cost': BILL_SUMMARY['dystrybucja_netto_zl'],
    'actual_fixed_costs': BILL_SUMMARY['akcyza_zl'],
    'actual_total_cost': BILL_SUMMARY['wartosc_brutto_zl'],
    'energy_exported_kwh': KWH_ODDANIE_TOTAL,
    'energy_exported_value': None,
    'bill_number': 'rozliczenie_01.2026_2026-01-01_31',
    'pdf_path': (
        f'{ROZLICZENIE_HEADER["tytul"]}|G12W|14kW|cennik=EE_GD_MIX_Eko_NowaEnergiaMix|'
        f'stawki_od=2026-01-01|'
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
        "DELETE FROM tauron_tariff WHERE valid_from = ? AND notes LIKE '%Rozliczenie 01.2026%'",
        ('2026-01-01',),
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
    print(f'   Akcyza {z["akcyza_zl"]:.2f} zł | Do zapłaty {z["do_zaplaty_po_depozycie"]:.2f} zł')
    print(f'   Termin płatności: {h["termin_platnosci"]}')

    print('\n📌 vs blankiet prognozy T/K1/0411004/25/6 (01–02/2026):')
    print('   Blankiet (2 mies.): 984 kWh, brutto 1127,34 zł')
    print(f'   Styczeń 2026:       {KWH_POBIOR_TOTAL:.0f} kWh pobór, brutto {z["wartosc_brutto_zl"]:.2f} zł')
    print(f'   → już {KWH_POBIOR_TOTAL - 984:.0f} kWh ponad prognozę na 2 miesiące')

    summary = importer.get_data_summary()
    print(f"\n   tauron_bills: {summary.get('tauron_bills', 0)} rekordów")
    importer.close()


if __name__ == '__main__':
    main()
