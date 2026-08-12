#!/usr/bin/env python
"""
Porównanie prognoz vs rzeczywistość — tabela do prezentacji (jak 16.07 → 29,5 kWh).

Użycie po peak 16:00 / wieczorem:
    python scripts/compare_day_forecasts.py --day 2026-07-17 --actual 36.5
    python scripts/compare_day_forecasts.py --day 2026-07-17 --actual 36.5 --save

Bez --actual: pokazuje prognozy + stan z bazy (dzień w toku).
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv()

import pandas as pd

HISTORY = 'data/processed/forecasts/forecast_history.csv'
OUT_DIR = 'data/processed/forecasts'


def _label_row(run_at: str, run_label: str, target: str) -> str:
    dt = pd.Timestamp(run_at)
    day = pd.Timestamp(target).date()
    d = dt.date()
    if d == day and run_label == 'daily':
        return 'Dziś 5:00'
    if d == day and run_label == 'midday':
        return 'Dziś 12:00 midday'
    if d == day and run_label == 'peak':
        return 'Dziś 16:00 peak'
    if d == day:
        return f'Dziś {dt.strftime("%H:%M")} ({run_label})'
    # previous day
    delta = (day - d).days
    if delta == 1 and run_label == 'daily':
        return 'Wczoraj 5:00'
    if delta == 1 and run_label == 'midday':
        return 'Wczoraj 12:00'
    if delta == 1 and run_label == 'peak':
        return 'Wczoraj 16:00'
    if delta == 1:
        return f'Wczoraj {dt.strftime("%H:%M")} ({run_label})'
    return f'{d.isoformat()} {dt.strftime("%H:%M")} ({run_label})'


def load_snapshots(target_day: str) -> pd.DataFrame:
    hist = pd.read_csv(HISTORY)
    hist = hist[hist['target_day'] == target_day].copy()
    if hist.empty:
        return hist
    # dedupe: last per (run_label, calendar day of run)
    from src.models.forecast_time import parse_forecast_ts

    hist['run_at'] = parse_forecast_ts(hist['run_at'])
    hist['run_date'] = hist['run_at'].dt.date.astype(str)
    hist = hist.sort_values('run_at').drop_duplicates(
        ['run_date', 'run_label'], keep='last',
    )
    hist['snapshot'] = [
        _label_row(a, lab, target_day)
        for a, lab in zip(hist['run_at'], hist['run_label'])
    ]
    # prefer presentation order
    order = {
        'Wczoraj 5:00': 0,
        'Wczoraj 12:00': 1,
        'Wczoraj 16:00': 2,
        'Dziś 5:00': 10,
        'Dziś 12:00 midday': 11,
        'Dziś 16:00 peak': 12,
    }
    hist['_ord'] = hist['snapshot'].map(lambda s: order.get(s, 50))
    hist = hist.sort_values(['_ord', 'run_at'])
    return hist.drop(columns=['_ord', 'run_date'])


def actual_from_db(target_day: str) -> tuple[float | None, str]:
    db = os.getenv('DATABASE_PATH', 'data/energy_model.db')
    if not os.path.exists(db):
        return None, 'brak bazy'
    conn = sqlite3.connect(db)
    tot = pd.read_sql(
        """
        SELECT timestamp, value FROM foxess_timeseries
        WHERE date(timestamp)=? AND variable='PVEnergyTotal'
        ORDER BY timestamp
        """,
        conn,
        params=(target_day,),
    )
    last_ts = pd.read_sql(
        "SELECT MAX(timestamp) ts FROM foxess_data WHERE date(timestamp)=?",
        conn,
        params=(target_day,),
    )
    conn.close()
    if len(tot) < 2:
        return None, 'za mało punktów PVEnergyTotal'
    delta = float(tot.iloc[-1]['value'] - tot.iloc[0]['value'])
    ts = str(last_ts['ts'].iloc[0] or tot.iloc[-1]['timestamp'])
    return round(delta, 2), f'PVEnergyTotal Δ do {ts}'


def grade(err_pct: float) -> str:
    a = abs(err_pct)
    if a <= 10:
        return 'bardzo dobrze'
    if a <= 20:
        return 'OK'
    if err_pct < -30:
        return 'najgorzej (za nisko)'
    if err_pct > 25:
        return 'za wysoko'
    if err_pct < 0:
        return 'za nisko'
    return 'za wysoko'


def build_table(snaps: pd.DataFrame, actual: float) -> pd.DataFrame:
    rows = []
    for _, r in snaps.iterrows():
        pred = float(r['predicted_kwh'])
        err = pred - actual
        pct = 100.0 * err / actual if actual else float('nan')
        rows.append({
            'Snapshot': r['snapshot'],
            'Prognoza_kWh': round(pred, 1),
            'Błąd_kWh': round(err, 1),
            'Błąd_pct': round(pct, 0),
            'Ocena': grade(pct),
            'run_at': r['run_at'],
            'run_label': r['run_label'],
        })
    return pd.DataFrame(rows)


def format_markdown(day: str, actual: float, table: pd.DataFrame, note: str = '') -> str:
    lines = [
        f'## {day} — ostatecznie **{actual:.1f} kWh**',
        '',
        'Porównanie z prognozami:',
        '',
        '| Snapshot | Prognoza | Błąd vs final | Ocena |',
        '|----------|----------|---------------|--------|',
    ]
    for _, r in table.iterrows():
        sign = '+' if r['Błąd_kWh'] >= 0 else '−'
        abs_e = abs(r['Błąd_kWh'])
        abs_p = abs(int(r['Błąd_pct']))
        lines.append(
            f"| **{r['Snapshot']}** | {r['Prognoza_kWh']:.1f} kWh | "
            f"{sign}{abs_e:.1f} kWh ({sign}{abs_p}%) | {r['Ocena']} |"
        )
    if note:
        lines.extend(['', note])
    # highlight best morning / worst
    if not table.empty:
        best = table.iloc[(table['Błąd_kWh'].abs()).argmin()]
        lines.extend([
            '',
            f"**Najbliżej finalu:** {best['Snapshot']} ({best['Prognoza_kWh']:.1f} kWh).",
        ])
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description='Tabela prognoza vs actual (prezentacja)')
    parser.add_argument('--day', default=date.today().isoformat(), help='YYYY-MM-DD')
    parser.add_argument(
        '--actual',
        type=float,
        default=None,
        help='Ostateczna produkcja z app FoxESS [kWh]',
    )
    parser.add_argument(
        '--from-db',
        action='store_true',
        help='Weź actual z PVEnergyTotal w bazie (może być niepełny w ciągu dnia)',
    )
    parser.add_argument('--save', action='store_true', help='Zapisz MD + CSV')
    args = parser.parse_args()

    snaps = load_snapshots(args.day)
    if snaps.empty:
        print(f'Brak wpisów w forecast_history dla {args.day}')
        sys.exit(1)

    print(f'=== Prognozy na {args.day} ===')
    print(snaps[['snapshot', 'run_at', 'run_label', 'predicted_kwh', 'actual_kwh_in_forecast']].to_string(index=False))

    db_actual, db_note = actual_from_db(args.day)
    if db_actual is not None:
        print(f'\nBaza ({db_note}): {db_actual} kWh')

    actual = args.actual
    source = 'app (--actual)'
    if actual is None and args.from_db and db_actual is not None:
        actual = db_actual
        source = db_note
    if actual is None:
        print(
            '\nℹ️  Podaj --actual X (z app) albo --from-db po syncu.\n'
            '   Po 16:00: python scripts/compare_day_forecasts.py '
            f'--day {args.day} --actual <kWh z app> --save'
        )
        return

    table = build_table(snaps, actual)
    note = f'*Źródło finalu: {source}. Wygenerowano {datetime.now().strftime("%Y-%m-%d %H:%M")}.*'
    md = format_markdown(args.day, actual, table, note=note)
    print('\n' + md)

    # short vs yesterday narrative hooks
    morning = table[table['Snapshot'] == 'Dziś 5:00']
    midday = table[table['Snapshot'] == 'Dziś 12:00 midday']
    if len(morning) and len(midday):
        m_err = float(morning.iloc[0]['Błąd_pct'])
        d_err = float(midday.iloc[0]['Błąd_pct'])
        print('\n--- Na prezentację ---')
        print(f'Dziś 5:00: błąd {m_err:+.0f}%')
        print(f'Dziś 12:00 midday: błąd {d_err:+.0f}%')
        if abs(d_err) < abs(m_err):
            print('→ Midday bliżej finalu niż rano.')
        elif d_err < -25:
            print('→ Midday mocno zaniżył (jak 16.07) — kontrast na slajd.')
        else:
            print('→ Midday stabilny względem rana — kontrast do 16.07 (−39%).')

    if args.save:
        os.makedirs(OUT_DIR, exist_ok=True)
        stamp = args.day.replace('-', '')
        csv_path = os.path.join(OUT_DIR, f'day_forecast_compare_{stamp}.csv')
        md_path = os.path.join(OUT_DIR, f'day_forecast_compare_{stamp}.md')
        table.to_csv(csv_path, index=False)
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md + '\n')
        print(f'\n✓ {csv_path}')
        print(f'✓ {md_path}')


if __name__ == '__main__':
    main()
