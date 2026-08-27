#!/usr/bin/env python3
"""
Routing decision: jasny → ensemble, pochmurny → CS4.

Zapisuje decyzję do CSV (paper-trade style).
"""

import argparse
import os
import sys
from datetime import date, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')


def get_forecast_cloud(target_date: str, db_path: str = DB_PATH) -> float:
    """Średni cloud z prognozy na dzień."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        '''
        SELECT AVG(cloud_cover_percent) as cloud_avg
        FROM weather_data
        WHERE date(timestamp) = ?
          AND data_source LIKE '%forecast%'
          AND cast(strftime('%H', timestamp) as integer) BETWEEN 6 AND 20
        ''',
        conn,
        params=(target_date,),
    )
    conn.close()
    if df.empty or pd.isna(df.iloc[0]['cloud_avg']):
        return 50.0  # default neutral
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


def main():
    parser = argparse.ArgumentParser(description='Routing decision jasny/pochmurny')
    parser.add_argument('--date', default='tomorrow', help='YYYY-MM-DD lub "tomorrow"')
    parser.add_argument('--threshold-cloud', type=float, default=30.0, help='Próg cloud (default 30)')
    parser.add_argument('--out', default='data/processed/routing_pick.csv', help='Output CSV')
    args = parser.parse_args()
    
    if args.date == 'tomorrow':
        target_date = (date.today() + timedelta(days=1)).isoformat()
    else:
        target_date = args.date
    
    decision = routing_decision(target_date, args.threshold_cloud)
    
    print("=" * 60)
    print(f"ROUTING DECISION: {target_date}")
    print("=" * 60)
    print(f"Cloud forecast avg: {decision['cloud_forecast_avg']}%")
    print(f"Regime:            {decision['regime']}")
    print(f"Model pick:        {decision['model_pick']}")
    print(f"Threshold:         {decision['threshold_cloud']}%")
    print("=" * 60)
    
    # Append do CSV
    df = pd.DataFrame([decision])
    if os.path.exists(args.out):
        df.to_csv(args.out, mode='a', header=False, index=False)
    else:
        df.to_csv(args.out, index=False)
    
    print(f"✅ Zapisano: {args.out}")


if __name__ == '__main__':
    main()
