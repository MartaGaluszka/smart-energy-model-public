"""
Korekta VAT za maj 2025 (okres 01/05–31/05/2025).

Do faktury VAT z dnia 09/06/2025. Przyczyna: depozyt / RCE.
Energia i dystrybucja bez zmian (34 kWh, 68,49 zł brutto).
Korekta depozytu: zwrot 1,16 zł (depozyt poprzednie 0,98 → 2,14 zł).

Uruchomienie:
    source venv/bin/activate
    python scripts/add_tauron_korekta_2025_05.py
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')

BILL_NUMBER = 'rozliczenie_05.2025_2025-05-01_31'

KOREKTA = {
    'okres': '01/05/2025 - 31/05/2025',
    'fv_bazowa': '2025-06-09',
    'przyczyna': 'depozyt/RCE — zaktualizowano wartość depozytu (rynkowa cena energii)',
    'pobor_kwh': 34.0,
    'energia_netto': 34.66,
    'dystrybucja_netto': 21.02,
    'razem_netto': 55.68,
    'razem_brutto': 68.49,
    'akcyza_zl': 0.28,
    'depozyt_prognoza': 0.0,
    'depozyt_okres': 0.0,
    'depozyt_poprzednie_policzono': 0.98,
    'depozyt_poprzednie_nalezalo': 2.14,
    'do_zaplaty_policzono': 67.51,
    'do_zaplaty_nalezalo': 66.35,
    'korekta_delta_brutto': -1.16,
    'do_zwrotu': 1.16,
}


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    row = cur.execute(
        'SELECT id, actual_total_kwh, actual_total_cost FROM tauron_bills WHERE bill_number = ?',
        (BILL_NUMBER,),
    ).fetchone()
    if not row:
        raise SystemExit(
            f'❌ Brak rekordu {BILL_NUMBER}. Najpierw uruchom add_tauron_rozliczenie_2025_05.py'
        )

    k = KOREKTA
    pdf_path = (
        f'Rozliczenie 05.2025|G12W|14kW|korekta_RCE|fv_bazowa={k["fv_bazowa"]}|'
        f'depozyt_poprzednie={k["depozyt_poprzednie_nalezalo"]}|'
        f'depozyt_poprzednie_policzono={k["depozyt_poprzednie_policzono"]}|'
        f'do_zaplaty_po_depozycie={k["do_zaplaty_nalezalo"]}|'
        f'korekta_delta_brutto={k["korekta_delta_brutto"]}|'
        f'do_zwrotu={k["do_zwrotu"]}'
    )

    cur.execute(
        '''
        UPDATE tauron_bills
        SET actual_fixed_costs = ?,
            pdf_path = ?
        WHERE bill_number = ?
        ''',
        (k['akcyza_zl'], pdf_path, BILL_NUMBER),
    )

    korekta_note = (
        f'Korekta VAT do fv 09/06/2025 | {k["okres"]}. '
        f'{k["przyczyna"]}. '
        f'Pobór {k["pobor_kwh"]:.0f} kWh, brutto {k["razem_brutto"]:.2f} zł (bez zmian). '
        f'Akcyza {k["akcyza_zl"]:.2f} zł. '
        f'Depozyt poprzednie: policzono {k["depozyt_poprzednie_policzono"]:.2f} zł → '
        f'należało {k["depozyt_poprzednie_nalezalo"]:.2f} zł. '
        f'Do zapłaty po depozycie: {k["do_zaplaty_nalezalo"]:.2f} zł. '
        f'Korekta: delta {k["korekta_delta_brutto"]:.2f} zł, do zwrotu {k["do_zwrotu"]:.2f} zł.'
    )

    updated = cur.execute(
        '''
        UPDATE tauron_tariff
        SET notes = notes || ' | ' || ?
        WHERE valid_from = '2025-05-01' AND notes LIKE '%Rozliczenie 05.2025%'
        ''',
        (korekta_note,),
    ).rowcount

    conn.commit()
    conn.close()

    print('=' * 70)
    print('Korekta VAT — maj 2025 (depozyt/RCE)')
    print(f'Okres {k["okres"]} | do fv z {k["fv_bazowa"]}')
    print('=' * 70)
    print(f'✅ Zaktualizowano: {BILL_NUMBER}')
    print(f'   Pobór: {k["pobor_kwh"]:.0f} kWh | Brutto: {k["razem_brutto"]:.2f} zł (bez zmian)')
    print(f'   Akcyza: {k["akcyza_zl"]:.2f} zł')
    print(
        f'   Depozyt poprzednie: {k["depozyt_poprzednie_policzono"]:.2f} zł → '
        f'{k["depozyt_poprzednie_nalezalo"]:.2f} zł'
    )
    print(f'   Do zapłaty po depozycie: {k["do_zaplaty_nalezalo"]:.2f} zł')
    print(
        f'   Korekta (delta): {k["korekta_delta_brutto"]:.2f} zł → '
        f'do zwrotu: {k["do_zwrotu"]:.2f} zł'
    )
    if updated:
        print('✅ Dopisano notatkę korekty do tauron_tariff (V 2025)')
    else:
        print('ℹ️  Brak wpisu tauron_tariff V/2025 do dopisania notatki')


if __name__ == '__main__':
    main()
