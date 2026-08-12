"""
Korekta VAT za październik 2025 (okres 01/10–31/10/2025).

Do faktury VAT z dnia 07/11/2025. Przyczyna: depozyt / RCE.
POLICZONO = NALEŻAŁO — korekta nie zmienia kWh ani kwot energii (delta 0 zł).
Uzupełnia istniejący rekord rozliczenia_10 o akcyzę i rozliczenie depozytu.

Uruchomienie:
    source venv/bin/activate
    python scripts/add_tauron_korekta_2025_10.py
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')

BILL_NUMBER = 'rozliczenie_10.2025_2025-10-01_31'

KOREKTA = {
    'okres': '01/10/2025 - 31/10/2025',
    'fv_bazowa': '2025-11-07',
    'przyczyna': 'depozyt/RCE — zaktualizowano wartość depozytu (rynkowa cena energii)',
    'pobor_kwh': 186.0,
    'energia_netto': 113.98,
    'dystrybucja_netto': 62.63,
    'razem_netto': 176.61,
    'razem_brutto': 217.24,
    'akcyza_zl': 1.24,
    'depozyt_prognoza': 0.0,
    'depozyt_okres': 0.0,
    'depozyt_poprzednie': 115.55,
    'depozyt_rozliczenie': 115.55,
    'do_zaplaty_po_depozycie': 101.69,
    'korekta_delta_brutto': 0.0,
    'do_zaplaty_korekta': 0.0,
    'termin_platnosci': '2026-01-26',
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
            f'❌ Brak rekordu {BILL_NUMBER}. Najpierw uruchom add_tauron_rozliczenie_2025_10.py'
        )

    pdf_path = (
        f'Rozliczenie 10.2025|G12W|14kW|korekta_RCE|fv_bazowa={KOREKTA["fv_bazowa"]}|'
        f'depozyt_poprzednie={KOREKTA["depozyt_poprzednie"]}|'
        f'do_zaplaty_po_depozycie={KOREKTA["do_zaplaty_po_depozycie"]}|'
        f'korekta_delta_brutto={KOREKTA["korekta_delta_brutto"]}'
    )

    cur.execute(
        '''
        UPDATE tauron_bills
        SET actual_fixed_costs = ?,
            pdf_path = ?
        WHERE bill_number = ?
        ''',
        (KOREKTA['akcyza_zl'], pdf_path, BILL_NUMBER),
    )

    korekta_note = (
        f'Korekta VAT do fv 07/11/2025 | {KOREKTA["okres"]}. '
        f'{KOREKTA["przyczyna"]}. '
        f'Pobór {KOREKTA["pobor_kwh"]:.0f} kWh, brutto {KOREKTA["razem_brutto"]:.2f} zł (bez zmian). '
        f'Akcyza {KOREKTA["akcyza_zl"]:.2f} zł. Depozyt poprzednie {KOREKTA["depozyt_poprzednie"]:.2f} zł, '
        f'do zapłaty po depozycie {KOREKTA["do_zaplaty_po_depozycie"]:.2f} zł. '
        f'Korekta: delta 0 zł, do zapłaty 0 zł.'
    )

    updated = cur.execute(
        '''
        UPDATE tauron_tariff
        SET notes = notes || ' | ' || ?
        WHERE valid_from = '2025-10-01' AND notes LIKE '%Rozliczenie 10.2025%'
        ''',
        (korekta_note,),
    ).rowcount

    conn.commit()
    conn.close()

    k = KOREKTA
    print('=' * 70)
    print('Korekta VAT — październik 2025 (depozyt/RCE)')
    print(f'Okres {k["okres"]} | do fv z {k["fv_bazowa"]}')
    print('=' * 70)
    print(f'✅ Zaktualizowano: {BILL_NUMBER}')
    print(f'   Pobór: {k["pobor_kwh"]:.0f} kWh | Brutto: {k["razem_brutto"]:.2f} zł (bez zmian)')
    print(f'   Akcyza: {k["akcyza_zl"]:.2f} zł')
    print(f'   Depozyt z poprzednich okresów: {k["depozyt_poprzednie"]:.2f} zł')
    print(f'   Do zapłaty po depozycie: {k["do_zaplaty_po_depozycie"]:.2f} zł')
    print(f'   Korekta (delta): {k["korekta_delta_brutto"]:.2f} zł → do zapłaty na korekcie: {k["do_zaplaty_korekta"]:.2f} zł')
    if updated:
        print('✅ Dopisano notatkę korekty do tauron_tariff (X 2025)')
    else:
        print('ℹ️  Brak wpisu tauron_tariff X/2025 do dopisania notatki')


if __name__ == '__main__':
    main()
