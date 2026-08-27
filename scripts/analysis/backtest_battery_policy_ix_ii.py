#!/usr/bin/env python3
"""BAT.4 — backtest kosztów baterii IX–II (polityka vs fakt).

Okno: 2025-09-01 … 2026-02-28 (jesień + zima z planu).

Polityki (advise-only, bez auto-apply):
  A — FAKT: rzeczywisty koszt importu z sieci w strefach G12w
  B — KONTRFAKT wąski: kWh „ładowanie baterii z sieci w drożej strefie”
      wycenione jak w taniej (przesunięcie FC do 22–6 / 13–15)
  B2 — KONTRFAKT doradczy: gdy w szczycie SoC < rezerwy sezonowej i jest import,
      zakładamy że nocny FC uzupełniłby brak do rezerwy → mniej importu w z1
      (przybliżenie; nie pełny replay SoC godzina×godzina)
  C — górna granica: cały import strefy 1 wyceniony jak strefa 2 (nierealne)

Uruchomienie:
  PYTHONPATH=. python scripts/analysis/backtest_battery_policy_ix_ii.py
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from src.optimization.battery_advisor import seasonal_soc_reserve
from src.optimization.g12w_tariff import classify_zone

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
DB = Path(os.getenv('DATABASE_PATH', ROOT / 'data' / 'energy_model.db'))

PERIOD_START = '2025-09-01'
PERIOD_END = '2026-02-28'  # inclusive day
BAT_CHARGE_KW = 0.5
GRID_IMPORT_MIN_KWH = 0.01
CAPACITY_KWH = 10.36


def _load_tariffs(conn: sqlite3.Connection) -> pd.DataFrame:
    t = pd.read_sql(
        """
        SELECT valid_from, price_zone1_day, price_zone2_night,
               distribution_zone1, distribution_zone2, oze_fee_kwh
        FROM tauron_tariff
        ORDER BY valid_from
        """,
        conn,
    )
    t['valid_from'] = pd.to_datetime(t['valid_from']).dt.date
    return t


def _rates_on(tariffs: pd.DataFrame, d) -> dict:
    row = tariffs[tariffs['valid_from'] <= d].iloc[-1]
    return {
        'z1': float(row['price_zone1_day']) + float(row['distribution_zone1'] or 0),
        'z2': float(row['price_zone2_night']) + float(row['distribution_zone2'] or 0),
        'oze': float(row['oze_fee_kwh'] or 0),
    }


def _parse_ts(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.replace(r'(\+|-)(\d{2}):(\d{2})$', '', regex=True)
    return pd.to_datetime(s, format='mixed')


def main() -> None:
    conn = sqlite3.connect(DB)
    tariffs = _load_tariffs(conn)

    df = pd.read_sql(
        """
        SELECT timestamp, grid_import_kwh, battery_power_kw, battery_soc_percent
        FROM foxess_data
        WHERE timestamp >= ? AND timestamp < date(?, '+1 day')
          AND grid_import_kwh IS NOT NULL
        ORDER BY timestamp
        """,
        conn,
        params=[PERIOD_START, PERIOD_END],
    )
    conn.close()

    if df.empty:
        raise SystemExit(f'Brak foxess_data dla {PERIOD_START}…{PERIOD_END}')

    df['timestamp'] = _parse_ts(df['timestamp'])
    df['day'] = df['timestamp'].dt.date
    df['zone'] = df['timestamp'].apply(classify_zone)
    df['rates'] = df['day'].apply(lambda d: _rates_on(tariffs, d))
    df['price'] = df.apply(lambda r: r['rates']['z1'] if r['zone'] == 1 else r['rates']['z2'], axis=1)
    df['oze'] = df['rates'].apply(lambda r: r['oze'])

    full_dt = df['timestamp'].diff().dt.total_seconds().div(3600).shift(-1)
    df['dt_h'] = full_dt.fillna(5 / 60).clip(lower=1 / 60, upper=0.25)

    df['cost_a'] = df['grid_import_kwh'] * (df['price'] + df['oze'])
    import_z1 = df.loc[df['zone'] == 1, 'grid_import_kwh'].sum()
    import_z2 = df.loc[df['zone'] == 2, 'grid_import_kwh'].sum()
    cost_a = float(df['cost_a'].sum())

    peak_fc = df[
        (df['zone'] == 1)
        & (df['battery_power_kw'].fillna(0) >= BAT_CHARGE_KW)
        & (df['grid_import_kwh'] >= GRID_IMPORT_MIN_KWH)
    ].copy()
    peak_fc['charge_kwh_est'] = peak_fc['battery_power_kw'] * peak_fc['dt_h']
    peak_fc['shiftable_kwh'] = peak_fc[['grid_import_kwh', 'charge_kwh_est']].min(axis=1).clip(lower=0)
    peak_fc['cost_fact'] = peak_fc['shiftable_kwh'] * (peak_fc['price'] + peak_fc['oze'])
    peak_fc['cost_cheap'] = peak_fc.apply(
        lambda r: r['shiftable_kwh'] * (r['rates']['z2'] + r['oze']),
        axis=1,
    )
    shiftable = float(peak_fc['shiftable_kwh'].sum())
    savings_b = float(peak_fc['cost_fact'].sum() - peak_fc['cost_cheap'].sum())
    cost_b = cost_a - savings_b

    b2_rows = []
    for day, g in df.groupby('day'):
        d = day if isinstance(day, date) else day
        reserve = seasonal_soc_reserve(d)
        peak = g[(g['zone'] == 1) & (g['grid_import_kwh'] > 0) & g['battery_soc_percent'].notna()]
        if peak.empty:
            continue
        low = peak[peak['battery_soc_percent'] < reserve]
        if low.empty:
            continue
        min_soc = float(low['battery_soc_percent'].min())
        deficit_kwh = max(0.0, (reserve - min_soc) / 100.0 * CAPACITY_KWH)
        import_while_low = float(low['grid_import_kwh'].sum())
        avoidable = min(deficit_kwh, import_while_low)
        if avoidable <= 0:
            continue
        rates = _rates_on(tariffs, d)
        save = avoidable * (rates['z1'] - rates['z2'])
        b2_rows.append(
            {
                'day': d,
                'reserve': reserve,
                'min_soc_peak': min_soc,
                'avoidable_kwh': avoidable,
                'savings_pln': save,
            }
        )
    b2 = pd.DataFrame(b2_rows)
    savings_b2 = float(b2['savings_pln'].sum()) if len(b2) else 0.0
    avoidable_b2 = float(b2['avoidable_kwh'].sum()) if len(b2) else 0.0
    cost_b2 = cost_a - savings_b2

    z1 = df[df['zone'] == 1].copy()
    cost_z1_fact = float((z1['grid_import_kwh'] * (z1['price'] + z1['oze'])).sum())
    cost_z1_as_z2 = float(
        z1.apply(lambda r: r['grid_import_kwh'] * (r['rates']['z2'] + r['oze']), axis=1).sum()
    )
    savings_c = cost_z1_fact - cost_z1_as_z2
    cost_c = cost_a - savings_c

    peak_fc['month'] = peak_fc['timestamp'].dt.to_period('M')
    if len(b2):
        b2['month'] = pd.to_datetime(b2['day']).dt.to_period('M')
    rows = []
    for month, g in df.groupby(df['timestamp'].dt.to_period('M')):
        iz1 = g.loc[g['zone'] == 1, 'grid_import_kwh'].sum()
        iz2 = g.loc[g['zone'] == 2, 'grid_import_kwh'].sum()
        ca = g['cost_a'].sum()
        pf = peak_fc[peak_fc['month'] == month]
        sb = float(pf['cost_fact'].sum() - pf['cost_cheap'].sum()) if len(pf) else 0.0
        sb2 = float(b2.loc[b2['month'] == month, 'savings_pln'].sum()) if len(b2) else 0.0
        rows.append(
            {
                'month': str(month),
                'import_z1_kwh': round(iz1, 1),
                'import_z2_kwh': round(iz2, 1),
                'cost_A_pln': round(ca, 2),
                'savings_B_pln': round(sb, 2),
                'savings_B2_pln': round(sb2, 2),
            }
        )
    monthly_df = pd.DataFrame(rows)

    print('=' * 72)
    print('BAT.4 — backtest kosztów baterii IX–II (advise-only)')
    print(f'Okno: {PERIOD_START} → {PERIOD_END}')
    print(f'DB: {DB}')
    print(f'Próbki foxess_data: {len(df):,}')
    print('=' * 72)
    print()
    print('Import z sieci (próbki 5-min, bez skalowania licznikiem):')
    print(f'  strefa 1 (drogo): {import_z1:,.1f} kWh')
    print(f'  strefa 2 (tanio): {import_z2:,.1f} kWh')
    print(f'  razem:            {import_z1 + import_z2:,.1f} kWh')
    print()
    print('Polityka A — FAKT:')
    print(f'  koszt A: {cost_a:,.2f} zł')
    print()
    print('Polityka B — przesuń drogie FC baterii → tania G12w:')
    print(f'  kWh do przesunięcia: {shiftable:,.1f} kWh')
    print(f'  oszczędność B: {savings_b:,.2f} zł → koszt B: {cost_b:,.2f} zł')
    print()
    print('Polityka B2 — trzymaj rezerwę sezonową w szczycie (doradca):')
    print(f'  dni z SoC < rezerwa w z1: {len(b2)}')
    print(f'  uniknięty import z1 (szacunek): {avoidable_b2:,.1f} kWh')
    print(f'  oszczędność B2 (spread z1−z2): {savings_b2:,.2f} zł → koszt: {cost_b2:,.2f} zł')
    print()
    print('Polityka C — górna granica (cały import z1 jak z2):')
    print(f'  oszczędność C: {savings_c:,.2f} zł → koszt C: {cost_c:,.2f} zł')
    print()
    print('Miesięcznie:')
    print(monthly_df.to_string(index=False))
    print()
    print('Werdykt (BAT.4):')
    print(
        f'  B (timing FC): ~{savings_b:.0f} zł — już prawie zero drogiego FC z sieci '
        f'({shiftable:.1f} kWh w całym IX–II).'
    )
    print(
        f'  B2 (rezerwa w szczycie): ~{savings_b2:.0f} zł przy {avoidable_b2:.0f} kWh — '
        f'to jest główny potencjał doradcy (BAT.3 / B2), nie przesuwanie FC.'
    )
    print(
        f'  C (max taryfowy): ~{savings_c:.0f} zł — sufit, gdyby cały import szczytowy '
        f'był w taniej (nierealne bez zmiany zużycia).'
    )
    print('  Auto-apply (B5/BAT.6) — nadal park; to walidacja, nie reguła live.')
    print()
    print(f'Wygenerowano: {datetime.now().isoformat(timespec="seconds")}')


if __name__ == '__main__':
    main()
