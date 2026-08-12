"""
Rozliczenie Tauron — maj 2026 (01/05/2026–31/05/2026).

Odczyt licznika 31/05/2026 (Z): pobór szczyt 7 + pozaszczyt 31 kWh; oddanie 280 + 123 kWh.

Uruchomienie:
    source venv/bin/activate
    python scripts/add_tauron_rozliczenie_2026_05.py
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
    'tytul': 'Rozliczenie 05.2026',
    'okres': '01/05/2026 - 31/05/2026',
    'numer_faktury': '/0006/26',
    'data_wystawienia': '2026-06-12',
    'rodzaj_rozliczenia': 'Net-billing',
    'czestotliwosc_rozliczenia': 'Co 1 miesiąc',
    'grupa_taryfowa': 'G12W',
    'moc_umowna_kw': 14,
    'nazwa_cennika': 'EE_GD MIX Eko_NowaEnergiaMix TS_9_Q1_01.03.25-28.02.34_prom',
    'termin_platnosci': '2026-06-26',
}

KWH_POBIOR_SZCZYT = 7.0
KWH_POBIOR_POZASZCZYT = 31.0
KWH_POBIOR_TOTAL = 38.0
KWH_ODDANIE_SZCZYT = 280.0
KWH_ODDANIE_POZASZCZYT = 123.0
KWH_ODDANIE_TOTAL = 403.0

BILL_SUMMARY = {
    'wartosc_netto_zl': 87.91,
    'vat_zl': 20.22,
    'wartosc_brutto_zl': 108.13,
    'srednia_cena_brutto_zl_kwh': 2.85,
    'energia_netto_zl': 42.89,
    'energia_brutto_zl': 52.76,
    'dystrybucja_netto_zl': 45.02,
    'dystrybucja_brutto_zl': 55.37,
    'akcyza_zl': 0.53,
    'depozyt_okres': 0.0,
    'depozyt_poprzednie': 18.61,
    'do_zaplaty_po_depozycie': 89.52,
}

TAURON_TARIFF = {
    'valid_from': '2026-05-01',
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
        f'{ROZLICZENIE_HEADER["tytul"]} | faktura {ROZLICZENIE_HEADER["numer_faktury"]} | '
        f'wystawiona {ROZLICZENIE_HEADER["data_wystawienia"]}. '
        f'{ROZLICZENIE_HEADER["okres"]}. {ROZLICZENIE_HEADER["rodzaj_rozliczenia"]}, '
        f'{ROZLICZENIE_HEADER["czestotliwosc_rozliczenia"].lower()}. '
        f'{ROZLICZENIE_HEADER["grupa_taryfowa"]}, moc {ROZLICZENIE_HEADER["moc_umowna_kw"]} kW. '
        f'Cennik: {ROZLICZENIE_HEADER["nazwa_cennika"]}. '
        'Energia szczyt 0,6244 / pozaszczyt 0,4163 zł/kWh netto. '
        'Opłaty stałe netto/mc: handlowa 25,61 + abonament 4,56 + mocowa 24,05 + '
        'składnik stały sieciowy 10,86 zł. '
        f'Odczyt 31/05/2026 (Z). Pobór {KWH_POBIOR_TOTAL:.0f} kWh (szczyt {KWH_POBIOR_SZCZYT:.0f} + '
        f'pozaszczyt {KWH_POBIOR_POZASZCZYT:.0f}), oddanie {KWH_ODDANIE_TOTAL:.0f} kWh '
        f'(szczyt {KWH_ODDANIE_SZCZYT:.0f} + pozaszczyt {KWH_ODDANIE_POZASZCZYT:.0f}). '
        f'Akcyza {BILL_SUMMARY["akcyza_zl"]:.2f} zł (od 106 kWh). '
        f'Depozyt okres {BILL_SUMMARY["depozyt_okres"]:.2f} zł, poprzednie '
        f'{BILL_SUMMARY["depozyt_poprzednie"]:.2f} zł, '
        f'do zapłaty {BILL_SUMMARY["do_zaplaty_po_depozycie"]:.2f} zł. '
        f'Śr. brutto {BILL_SUMMARY["srednia_cena_brutto_zl_kwh"]:.2f} zł/kWh. '
        'Analogiczny okres rok wcześniej: 34 kWh.'
    ),
}

TAURON_BILL = {
    'bill_date': '2026-05-31',
    'billing_period_start': '2026-05-01',
    'billing_period_end': '2026-05-31',
    'actual_zone1_kwh': KWH_POBIOR_SZCZYT,
    'actual_zone2_kwh': KWH_POBIOR_POZASZCZYT,
    'actual_total_kwh': KWH_POBIOR_TOTAL,
    'actual_energy_cost': BILL_SUMMARY['energia_netto_zl'],
    'actual_distribution_cost': BILL_SUMMARY['dystrybucja_netto_zl'],
    'actual_fixed_costs': BILL_SUMMARY['akcyza_zl'],
    'actual_total_cost': BILL_SUMMARY['wartosc_brutto_zl'],
    'energy_exported_kwh': KWH_ODDANIE_TOTAL,
    # Wartość eksportu po RCE (net-billing) — szacunek FoxESS+RCE, nie stała taryfa G12W.
    # Uruchom: python scripts/calculate_prosumer_deposit.py --start 2026-05-01 --end 2026-05-31
    'energy_exported_value': 71.46,
    'bill_number': 'rozliczenie_05.2026_2026-05-01_31',
    'pdf_path': (
        f'{ROZLICZENIE_HEADER["tytul"]}|numer_faktury={ROZLICZENIE_HEADER["numer_faktury"]}|'
        f'data_wystawienia={ROZLICZENIE_HEADER["data_wystawienia"]}|'
        f'rodzaj_rozliczenia={ROZLICZENIE_HEADER["rodzaj_rozliczenia"]}|'
        f'G12W|14kW|cennik={ROZLICZENIE_HEADER["nazwa_cennika"]}|'
        f'depozyt_okres={BILL_SUMMARY["depozyt_okres"]}|'
        f'depozyt_poprzednie={BILL_SUMMARY["depozyt_poprzednie"]}|'
        f'do_zaplaty_po_depozycie={BILL_SUMMARY["do_zaplaty_po_depozycie"]}|'
        f'termin_platnosci={ROZLICZENIE_HEADER["termin_platnosci"]}'
    ),
}


METER_READING = {
    'period_start': '2026-05-01',
    'period_end': '2026-05-31',
    'import_kwh': KWH_POBIOR_TOTAL,
    'export_kwh': KWH_ODDANIE_TOTAL,
    'import_zone1_kwh': KWH_POBIOR_SZCZYT,
    'import_zone2_kwh': KWH_POBIOR_POZASZCZYT,
    'export_zone1_kwh': KWH_ODDANIE_SZCZYT,
    'export_zone2_kwh': KWH_ODDANIE_POZASZCZYT,
    'source': 'licznik_tauron',
    'notes': (
        f'{ROZLICZENIE_HEADER["tytul"]} | faktura {ROZLICZENIE_HEADER["numer_faktury"]} | '
        f'odczyt 31/05/2026 (Z)'
    ),
}


def _replace_prior(conn: sqlite3.Connection) -> None:
    conn.execute(
        'DELETE FROM tauron_bills WHERE bill_number = ?',
        (TAURON_BILL['bill_number'],),
    )
    conn.execute(
        "DELETE FROM tauron_tariff WHERE valid_from = ? AND notes LIKE '%Rozliczenie 05.2026%'",
        ('2026-05-01',),
    )
    conn.commit()


def _upsert_meter_reading(conn: sqlite3.Connection) -> None:
    row = METER_READING
    conn.execute(
        '''
        INSERT OR REPLACE INTO meter_readings (
            period_start, period_end, import_kwh, export_kwh,
            import_zone1_kwh, import_zone2_kwh, export_zone1_kwh, export_zone2_kwh,
            source, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            row['period_start'], row['period_end'],
            row['import_kwh'], row['export_kwh'],
            row['import_zone1_kwh'], row['import_zone2_kwh'],
            row['export_zone1_kwh'], row['export_zone2_kwh'],
            row['source'], row['notes'],
        ),
    )
    conn.commit()


def main():
    conn = sqlite3.connect(DB_PATH)
    _replace_prior(conn)
    _upsert_meter_reading(conn)
    conn.close()

    importer = EnergyDataImporter()
    h = ROZLICZENIE_HEADER
    z = BILL_SUMMARY

    print('=' * 70)
    print(h['tytul'])
    print(f'Faktura {h["numer_faktury"]} | wystawiona {h["data_wystawienia"]}')
    print(f'{h["okres"]} | {h["rodzaj_rozliczenia"]} | {h["grupa_taryfowa"]} | moc {h["moc_umowna_kw"]} kW')
    print(f'Cennik: {h["nazwa_cennika"]}')
    print('=' * 70)

    importer.import_tauron_tariff(data_dict=TAURON_TARIFF)
    print('✅ tauron_tariff')

    importer.import_tauron_bill(data_dict=TAURON_BILL)
    print('✅ tauron_bills')
    print('✅ meter_readings (maj 2026)')

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
    print('   Marzec:   223 / 246 kWh → 254,36 zł')
    print('   Kwiecień: 134 / 288 kWh → 188,82 zł')
    print(f'   Maj:       {KWH_POBIOR_TOTAL:.0f} / {KWH_ODDANIE_TOTAL:.0f} kWh → {z["wartosc_brutto_zl"]:.2f} zł')

    summary = importer.get_data_summary()
    print(f"\n   tauron_bills: {summary.get('tauron_bills', 0)} rekordów")
    importer.close()


if __name__ == '__main__':
    main()
