#!/usr/bin/env python3
"""
Routing decision: jasny → ensemble, pochmurny → CS4.

Zapisuje decyzję do CSV (paper-trade style). Upsert po dacie (bez duplikatów).
Cloud z OpenMeteo-forecast (ICON primary) — bez mieszania z ensemble.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')


def get_forecast_cloud(target_date: str, db_path: str = DB_PATH) -> float:
    """Średni cloud z prognozy ICON (primary) na dzień, godz. 6–20."""
    import sqlite3

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        '''
        SELECT AVG(cloud_cover_percent) as cloud_avg
        FROM weather_data
        WHERE date(timestamp) = ?
          AND data_source = 'OpenMeteo-forecast'
          AND cast(strftime('%H', timestamp) as integer) BETWEEN 6 AND 20
        ''',
        conn,
        params=(target_date,),
    )
    conn.close()
    if df.empty or pd.isna(df.iloc[0]['cloud_avg']):
        return 50.0
    return float(df.iloc[0]['cloud_avg'])


def routing_decision(target_date: str, threshold_cloud: float = 30.0) -> dict:
    """Decyzja routing: ensemble vs CS4."""
    cloud_avg = get_forecast_cloud(target_date)

    if cloud_avg < threshold_cloud:
        regime = 'clear'
        model = 'ensemble'
    else:
        regime = 'cloudy'
        model = 'CS4'

    return {
        'date': target_date,
        'cloud_forecast_avg': round(cloud_avg, 1),
        'regime': regime,
        'model_pick': model,
        'threshold_cloud': threshold_cloud,
    }


def _upsert_csv(path: str, rows: list[dict]) -> None:
    new_df = pd.DataFrame(rows)
    if os.path.exists(path):
        old = pd.read_csv(path)
        old = old[~old['date'].astype(str).isin(new_df['date'].astype(str))]
        out = pd.concat([old, new_df], ignore_index=True)
    else:
        out = new_df
    out = out.sort_values('date')
    out.to_csv(path, index=False)


def main():
    parser = argparse.ArgumentParser(description='Routing decision jasny/pochmurny')
    parser.add_argument('--date', default='today', help='YYYY-MM-DD | today | tomorrow')
    parser.add_argument(
        '--also-next',
        type=int,
        default=0,
        help='Dodatkowe dni po --date (np. 2 → dziś+jutro+pojutrze)',
    )
    parser.add_argument('--threshold-cloud', type=float, default=30.0, help='Próg cloud (default 30)')
    parser.add_argument('--out', default='data/processed/routing_pick.csv', help='Output CSV')
    args = parser.parse_args()

    if args.date == 'tomorrow':
        start = date.today() + timedelta(days=1)
    elif args.date == 'today':
        start = date.today()
    else:
        start = date.fromisoformat(args.date)

    decisions = []
    for i in range(0, max(0, args.also_next) + 1):
        target = (start + timedelta(days=i)).isoformat()
        decision = routing_decision(target, args.threshold_cloud)
        decisions.append(decision)
        print('=' * 60)
        print(f"ROUTING DECISION: {target}")
        print('=' * 60)
        print(f"Cloud forecast avg: {decision['cloud_forecast_avg']}%")
        print(f"Regime:            {decision['regime']}")
        print(f"Model pick:        {decision['model_pick']}")
        print(f"Threshold:         {decision['threshold_cloud']}%")

    _upsert_csv(args.out, decisions)
    print('=' * 60)
    print(f"✅ Zapisano {len(decisions)} wierszy → {args.out}")


if __name__ == '__main__':
    main()
