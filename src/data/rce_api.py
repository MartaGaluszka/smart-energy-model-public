"""
Pobieranie RCE (Rynkowa Cena Energii) z API PSE.

Dokumentacja: https://api.raporty.pse.pl/ — raport rce-pln.
Ceny w PLN/MWh, interwały 15-minutowe; do net-billingu agregujemy do godzin.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from typing import Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)

RCE_API_URL = 'https://api.raporty.pse.pl/api/rce-pln'
DEFAULT_DB = 'data/energy_model.db'

RCE_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS rce_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    period_label VARCHAR(20),
    business_date DATE NOT NULL,
    rce_pln_mwh REAL NOT NULL,
    rce_pln_kwh REAL NOT NULL,
    source VARCHAR(50) DEFAULT 'pse_api',
    UNIQUE(timestamp, source)
);
CREATE INDEX IF NOT EXISTS idx_rce_business_date ON rce_prices(business_date);
CREATE INDEX IF NOT EXISTS idx_rce_timestamp ON rce_prices(timestamp);
'''


def ensure_rce_table(conn: sqlite3.Connection) -> None:
    conn.executescript(RCE_TABLE_SQL)
    conn.commit()


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=120) as resp:
        return json.loads(resp.read().decode())


def fetch_rce_day(business_date: Union[date, str]) -> pd.DataFrame:
    """Pobiera 15-min RCE dla jednej doby handlowej."""
    day = business_date.isoformat() if isinstance(business_date, date) else business_date
    filt = f"business_date eq '{day}'"
    encoded = urllib.parse.quote(filt, safe="'")
    url = f'{RCE_API_URL}?$filter={encoded}'
    payload = _get_json(url)
    rows = payload.get('value') or []
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df['timestamp'] = pd.to_datetime(df['dtime'])
    df['business_date'] = df['business_date'].astype(str)
    df['period_label'] = df['period']
    df['rce_pln_mwh'] = df['rce_pln'].astype(float)
    df['rce_pln_kwh'] = df['rce_pln_mwh'] / 1000.0
    df['source'] = 'pse_api'
    return df[['timestamp', 'period_label', 'business_date', 'rce_pln_mwh', 'rce_pln_kwh', 'source']]


def fetch_rce_range(start_date: str, end_date: str) -> pd.DataFrame:
    """Pobiera RCE dzień po dniu (API filtruje po business_date)."""
    start = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()
    chunks = []
    day = start
    while day <= end:
        df = fetch_rce_day(day)
        if not df.empty:
            chunks.append(df)
        day += timedelta(days=1)
        time.sleep(0.05)
    if not chunks:
        return pd.DataFrame()
    return pd.concat(chunks, ignore_index=True)


def save_rce_to_db(
    df: pd.DataFrame,
    db_path: str = DEFAULT_DB,
) -> int:
    """Zapisuje RCE do rce_prices (INSERT OR REPLACE)."""
    if df.empty:
        return 0

    conn = sqlite3.connect(db_path)
    ensure_rce_table(conn)
    rows = 0
    for _, r in df.iterrows():
        conn.execute(
            '''
            INSERT OR REPLACE INTO rce_prices (
                timestamp, period_label, business_date,
                rce_pln_mwh, rce_pln_kwh, source
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (
                r['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                r.get('period_label'),
                r['business_date'],
                r['rce_pln_mwh'],
                r['rce_pln_kwh'],
                r.get('source', 'pse_api'),
            ),
        )
        rows += 1
    conn.commit()
    conn.close()
    return rows


def load_rce_hourly(
    db_path: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Godzinowa średnia RCE [zł/kWh] z kwadransów PSE."""
    conn = sqlite3.connect(db_path)
    ensure_rce_table(conn)
    df = pd.read_sql_query(
        '''
        SELECT timestamp, business_date, rce_pln_kwh
        FROM rce_prices
        WHERE business_date BETWEEN ? AND ?
        ORDER BY timestamp
        ''',
        conn,
        params=(start_date, end_date),
    )
    conn.close()
    if df.empty:
        return df

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    # dtime w API = koniec okresu 15-min → przypisz do godziny początkowej
    df['hour'] = (df['timestamp'] - pd.Timedelta(minutes=15)).dt.floor('h')
    hourly = (
        df.groupby('hour', as_index=False)
        .agg(rce_pln_kwh=('rce_pln_kwh', 'mean'), business_date=('business_date', 'first'))
    )
    return hourly


def load_grid_exchange_hourly(
    db_path: str,
    start_date: str,
    end_date: str,
    source: str = 'foxess',
) -> pd.DataFrame:
    """
    Godzinowe import/export [kWh] z FoxESS lub licznika Tauron.

    source: 'foxess' | 'meter' | 'auto' (meter jeśli jest, inaczej foxess)
    """
    conn = sqlite3.connect(db_path)

    if source in ('meter', 'auto'):
        try:
            meter = pd.read_sql_query(
                '''
                SELECT
                    strftime('%Y-%m-%d %H:00:00', timestamp) AS hour,
                    SUM(CASE WHEN flow = 'import' THEN kwh ELSE 0 END) AS import_kwh,
                    SUM(CASE WHEN flow = 'export' THEN kwh ELSE 0 END) AS export_kwh
                FROM meter_hourly
                WHERE date(timestamp) BETWEEN ? AND ?
                GROUP BY hour
                ORDER BY hour
                ''',
                conn,
                params=(start_date, end_date),
            )
        except sqlite3.OperationalError:
            meter = pd.DataFrame()

        if source == 'meter' and not meter.empty:
            conn.close()
            meter['hour'] = pd.to_datetime(meter['hour'])
            meter['data_source'] = 'meter_hourly'
            return meter

        if source == 'auto' and not meter.empty:
            conn.close()
            meter['hour'] = pd.to_datetime(meter['hour'])
            meter['data_source'] = 'meter_hourly'
            return meter

    fox = pd.read_sql_query(
        '''
        SELECT
            strftime('%Y-%m-%d %H:00:00', timestamp) AS hour,
            SUM(COALESCE(grid_import_kwh, 0)) AS import_kwh,
            SUM(COALESCE(grid_export_kwh, 0)) AS export_kwh
        FROM foxess_data
        WHERE date(timestamp) BETWEEN ? AND ?
        GROUP BY hour
        ORDER BY hour
        ''',
        conn,
        params=(start_date, end_date),
    )
    conn.close()
    fox['hour'] = pd.to_datetime(fox['hour'])
    fox['data_source'] = 'foxess_data'
    return fox
