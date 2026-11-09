#!/usr/bin/env python3
"""Shadow cap porannej sumy @05 — nie zmienia prognozy w apce ani launchd.

Reguła (raport), po przeglądzie progów 70–95% na closeoutach do 08.11:
  - cięcie tylko gdy chmura 6–20 ≥ 88% **i** ENS @05 ≤ 10 kWh
  - bias = średnia (ENS − Fox) z poprzednich 28 dni o chmurze ≥ 88%
    (≥ 3 takie dni, bias obcięty do ≥ 0)
  - sam próg 90% omija 01.11 (88,96%). Samo obniżenie progu bez sufitu ENS
    tnie dni jasne z „fałszywą” wysoką chmurą NWP (m.in. 01.10, 10.10).
  - inaczej cap = surowy ENS

Wyjście: data/processed/forecasts/morning_cloud_cap_shadow.csv

Nie włącza FORECAST_OPERATIONAL_ADJUST. Do apki dopiero po 2 tygodniach,
gdy cap jest bliżej Foxa na pochmurnych i nie psuje jasnych.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

VALIDATION = ROOT / 'data/processed/forecasts/forecast_validation.csv'
DB = ROOT / 'data/energy_model.db'
OUT = ROOT / 'data/processed/forecasts/morning_cloud_cap_shadow.csv'

CLOUD_MIN = 88.0
ENS_MAX_KWH = 10.0
LOOKBACK_DAYS = 28
MIN_BIAS_DAYS = 3


def _cloud(db: Path) -> pd.DataFrame:
    if not db.exists():
        return pd.DataFrame(columns=['day', 'cloud'])
    con = sqlite3.connect(str(db))
    try:
        w = pd.read_sql_query(
            """
            SELECT date(timestamp) AS day,
                   AVG(cloud_cover_percent) AS cloud
            FROM weather_data
            WHERE CAST(strftime('%H', timestamp) AS INTEGER) BETWEEN 6 AND 20
            GROUP BY 1
            """,
            con,
        )
    finally:
        con.close()
    w['day'] = pd.to_datetime(w['day'])
    return w


def build_shadow(validation: Path = VALIDATION, db: Path = DB) -> pd.DataFrame:
    df = pd.read_csv(validation)
    df['target_day'] = pd.to_datetime(df['target_day'])
    if 'closeout_at' in df.columns:
        df['closeout_at'] = pd.to_datetime(df['closeout_at'])
        df = df.sort_values('closeout_at').groupby('target_day', as_index=False).last()
    df['fox'] = pd.to_numeric(df['actual_pv_total'], errors='coerce')
    df['ens'] = pd.to_numeric(df['predicted_daily_raw'], errors='coerce')
    df = df.dropna(subset=['fox', 'ens']).sort_values('target_day')
    df = df.merge(_cloud(db), left_on='target_day', right_on='day', how='left')

    rows = []
    for _, r in df.iterrows():
        day = r['target_day']
        window = df[
            (df['target_day'] < day)
            & (df['target_day'] >= day - pd.Timedelta(days=LOOKBACK_DAYS))
            & (df['cloud'] >= CLOUD_MIN)
        ]
        bias = None
        if len(window) >= MIN_BIAS_DAYS:
            bias = float((window['ens'] - window['fox']).mean())
            bias = max(0.0, bias)
        cloudy = pd.notna(r['cloud']) and float(r['cloud']) >= CLOUD_MIN
        low_ens = float(r['ens']) <= ENS_MAX_KWH
        applied = bool(cloudy and low_ens and bias is not None and bias > 0)
        cap = float(r['ens'] - bias) if applied else float(r['ens'])
        cap = max(0.0, cap)
        rows.append({
            'target_day': day.date().isoformat(),
            'fox_kwh': round(float(r['fox']), 2),
            'ens_kwh': round(float(r['ens']), 2),
            'cloud_6_20': None if pd.isna(r['cloud']) else round(float(r['cloud']), 1),
            'bias_kwh': None if bias is None else round(bias, 2),
            'cap_applied': applied,
            'cap_kwh': round(cap, 2),
            'abs_err_ens': round(abs(float(r['ens']) - float(r['fox'])), 2),
            'abs_err_cap': round(abs(cap - float(r['fox'])), 2),
        })
    return pd.DataFrame(rows)


def main() -> None:
    out = build_shadow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    nov = out[out['target_day'] >= '2026-11-01']
    print(f'✓ {OUT.relative_to(ROOT)}  wierszy {len(out)}')
    if nov.empty:
        return
    print('Listopad (shadow, nie apka):')
    print(nov.to_string(index=False))
    fox = nov['fox_kwh'].sum()
    if fox > 0:
        wape_ens = nov['abs_err_ens'].sum() / fox * 100
        wape_cap = nov['abs_err_cap'].sum() / fox * 100
        print(f'WAPE 01.11+  ENS {wape_ens:.1f}%   cap {wape_cap:.1f}%')
    print('Apka bez zmian. FORECAST_OPERATIONAL_ADJUST zostaje wyłączony.')


if __name__ == '__main__':
    main()
