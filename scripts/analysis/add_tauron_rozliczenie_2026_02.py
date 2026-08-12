"""
Rozliczenie Tauron — luty 2026 (01/02/2026–28/02/2026).

Stawki energii na fakturze: szczyt 0,6244 / pozaszczyt 0,4163 zł/kWh netto.
Odczyt licznika 28/02/2026 (Z): pobór szczyt 59 + pozaszczyt 684 kWh; oddanie 38 + 33 kWh.

Uruchomienie:
    source venv/bin/activate
    python scripts/add_tauron_rozliczenie_2026_02.py
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
    'tytul': 'Rozliczenie 02.2026',
    'okres': '01/02/2026 - 28/02/2026',
    'grupa_taryfowa': 'G12W',
    'moc_umowna_kw': 14,
    'nazwa_cennika': 'EE_GD MIX Eko_NowaEnergiaMix TS_9_Q1_01.03.25-28.02.34',
    'termin_platnosci': '2026-04-24',
}

# Odczyt zdalny 28/02/2026 (Z) — ilości zgodne z pozycjami na fakturze
KWH_POBIOR_SZCZYT = 59.0
KWH_POBIOR_POZASZCZYT = 684.0
KWH_POBIOR_TOTAL = 743.0
KWH_ODDANIE_SZCZYT = 38.0
KWH_ODDANIE_POZASZCZYT = 33.0
KWH_ODDANIE_TOTAL = 71.0

BILL_SUMMARY = {
    'wartosc_netto_zl': 473.47,
    'vat_zl': 108.89,
    'wartosc_brutto_zl': 582.36,
    'srednia_cena_brutto_zl_kwh': 0.78,
    'energia_netto_zl': 347.20,
    'energia_brutto_zl': 427.05,
    'dystrybucja_netto_zl': 126.27,
    'dystrybucja_brutto_zl': 155.31,
    'akcyza_zl': 4.02,
    'depozyt_okres': 0.0,
    'depozyt_poprzednie': 5.01,
    'do_zaplaty_po_depozycie': 577.35,
}

TAURON_TARIFF = {
    'valid_from': '2026-02-01',
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
        'Opłata handlowa 25,61 zł, przejściowa 0,00 zł, opłata mocowa 24,05 zł netto. '
        f'Odczyt 28/02/2026 (Z). Pobór {KWH_POBIOR_TOTAL:.0f} kWh (szczyt {KWH_POBIOR_SZCZYT:.0f} + '
        f'pozaszczyt {KWH_POBIOR_POZASZCZYT:.0f}), oddanie {KWH_ODDANIE_TOTAL:.0f} kWh '
        f'(szczyt {KWH_ODDANIE_SZCZYT:.0f} + pozaszczyt {KWH_ODDANIE_POZASZCZYT:.0f}). '
        f'Akcyza {BILL_SUMMARY["akcyza_zl"]:.2f} zł (od 804 kWh). '
        f'Depozyt poprzednie {BILL_SUMMARY["depozyt_poprzednie"]:.2f} zł, '
        f'do zapłaty {BILL_SUMMARY["do_zaplaty_po_depozycie"]:.2f} zł. '
        f'Śr. brutto {BILL_SUMMARY["srednia_cena_brutto_zl_kwh"]:.2f} zł/kWh.'
    ),
}

TAURON_BILL = {
    'bill_date': '2026-02-28',
    'billing_period_start': '2026-02-01',
    'billing_period_end': '2026-02-28',
    'actual_zone1_kwh': KWH_POBIOR_SZCZYT,
    'actual_zone2_kwh': KWH_POBIOR_POZASZCZYT,
    'actual_total_kwh': KWH_POBIOR_TOTAL,
    'actual_energy_cost': BILL_SUMMARY['energia_netto_zl'],
    'actual_distribution_cost': BILL_SUMMARY['dystrybucja_netto_zl'],
    'actual_fixed_costs': BILL_SUMMARY['akcyza_zl'],
    'actual_total_cost': BILL_SUMMARY['wartosc_brutto_zl'],
    'energy_exported_kwh': KWH_ODDANIE_TOTAL,
    'energy_exported_value': None,
    'bill_number': 'rozliczenie_02.2026_2026-02-01_28',
    'pdf_path': (
        f'{ROZLICZENIE_HEADER["tytul"]}|G12W|14kW|cennik=EE_GD_MIX_Eko_NowaEnergiaMix|'
        f'stawki_energii=0.6244/0.4163|'
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
        "DELETE FROM tauron_tariff WHERE valid_from = ? AND notes LIKE '%Rozliczenie 02.2026%'",
        ('2026-02-01',),
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

    print('\n📌 vs blankiet prognozy T/K1/0411004/25/6 (01–02/2026):')
    print('   Blankiet (2 mies.): 984 kWh, brutto 1127,34 zł')
    print('   Styczeń 2026:       1175 kWh, brutto 996,70 zł')
    print(f'   Luty 2026:          {KWH_POBIOR_TOTAL:.0f} kWh, brutto {z["wartosc_brutto_zl"]:.2f} zł')
    print(f'   I+II łącznie:       {1175 + KWH_POBIOR_TOTAL:.0f} kWh, brutto {996.70 + z["wartosc_brutto_zl"]:.2f} zł')

    summary = importer.get_data_summary()
    print(f"\n   tauron_bills: {summary.get('tauron_bills', 0)} rekordów")
    importer.close()


if __name__ == '__main__':
    main()
