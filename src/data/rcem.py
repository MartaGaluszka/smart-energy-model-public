"""
RCEm — rynkowa miesięczna cena energii (PSE).

Źródło oficjalne: https://www.pse.pl/oire/rcem-rynkowa-miesieczna-cena-energii-elektrycznej
Brak publicznego API — wartości z publikacji PSE (seed) lub średnia z rce_prices w bazie.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Optional, Union

import pandas as pd

DEFAULT_DB = 'data/energy_model.db'
SEED_PATH = Path(__file__).resolve().parents[2] / 'data' / 'rcem_pse_seed.json'

RCEM_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS rcem_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_month VARCHAR(7) NOT NULL,
    rce_pln_mwh REAL NOT NULL,
    rce_pln_kwh REAL NOT NULL,
    corrected_rce_pln_mwh REAL,
    corrected_rce_pln_kwh REAL,
    publication_date DATE,
    source VARCHAR(50) DEFAULT 'pse_seed',
    notes TEXT,
    UNIQUE(period_month, source)
);
CREATE INDEX IF NOT EXISTS idx_rcem_period ON rcem_prices(period_month);
'''


def ensure_rcem_table(conn: sqlite3.Connection) -> None:
    conn.executescript(RCEM_TABLE_SQL)
    conn.commit()


def _month_key(d: Union[str, pd.Timestamp]) -> str:
    ts = pd.Timestamp(d)
    return ts.strftime('%Y-%m')


def load_seed() -> dict:
    if not SEED_PATH.is_file():
        return {}
    with open(SEED_PATH, encoding='utf-8') as f:
        payload = json.load(f)
    return {k: v for k, v in payload.items() if k.startswith('20')}


def save_rcem_to_db(
    period_month: str,
    rce_pln_mwh: float,
    db_path: str = DEFAULT_DB,
    corrected_rce_pln_mwh: Optional[float] = None,
    publication_date: Optional[str] = None,
    source: str = 'pse_seed',
    notes: Optional[str] = None,
) -> None:
    conn = sqlite3.connect(db_path)
    ensure_rcem_table(conn)
    conn.execute(
        '''
        INSERT OR REPLACE INTO rcem_prices (
            period_month, rce_pln_mwh, rce_pln_kwh,
            corrected_rce_pln_mwh, corrected_rce_pln_kwh,
            publication_date, source, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            period_month,
            rce_pln_mwh,
            rce_pln_mwh / 1000.0,
            corrected_rce_pln_mwh,
            corrected_rce_pln_mwh / 1000.0 if corrected_rce_pln_mwh is not None else None,
            publication_date,
            source,
            notes,
        ),
    )
    conn.commit()
    conn.close()


def import_seed_to_db(db_path: str = DEFAULT_DB) -> int:
    """Importuje oficjalne RCEm z data/rcem_pse_seed.json."""
    seed = load_seed()
    for month, row in seed.items():
        save_rcem_to_db(
            month,
            row['rce_pln_mwh'],
            db_path=db_path,
            corrected_rce_pln_mwh=row.get('corrected_rce_pln_mwh'),
            source='pse_official',
            notes='PSE RCEm — publikacja pse.pl/oire/rcem',
        )
    return len(seed)


def compute_rcem_from_hourly(
    db_path: str,
    period_month: str,
) -> Optional[float]:
    """
    Średnia arytmetyczna kwadransowych RCE z rce_prices za dany miesiąc kalendarzowy.
    Przybliżenie oficjalnej RCEm (średnia ważona PSE).
    """
    start = f'{period_month}-01'
    end = (pd.Timestamp(start) + pd.offsets.MonthEnd(0)).strftime('%Y-%m-%d')
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            '''
            SELECT AVG(rce_pln_mwh), COUNT(*)
            FROM rce_prices
            WHERE business_date BETWEEN ? AND ?
            ''',
            (start, end),
        ).fetchone()
    except sqlite3.OperationalError:
        conn.close()
        return None
    conn.close()
    if not row or not row[0] or row[1] == 0:
        return None
    return round(float(row[0]), 2)


def update_rcem_from_hourly(db_path: str, start_month: str, end_month: str) -> int:
    """Oblicza RCEm z rce_prices i zapisuje jako source=computed_from_rce."""
    cur = pd.Timestamp(f'{start_month}-01')
    end = pd.Timestamp(f'{end_month}-01')
    n = 0
    while cur <= end:
        month = cur.strftime('%Y-%m')
        avg = compute_rcem_from_hourly(db_path, month)
        if avg is not None:
            save_rcem_to_db(
                month,
                avg,
                db_path=db_path,
                source='computed_from_rce',
                notes=f'Średnia z {month} kwadransów rce_prices',
            )
            n += 1
        cur += pd.offsets.MonthBegin(1)
    return n


def get_rcem(
    period_month: str,
    db_path: str = DEFAULT_DB,
    prefer: str = 'official',
    use_corrected: bool = True,
) -> Optional[dict]:
    """
    Zwraca RCEm dla YYYY-MM.

    prefer: 'official' | 'computed' | 'any'
    use_corrected: użyj skorygowanej RCEm jeśli dostępna (PSE).
    """
    conn = sqlite3.connect(db_path)
    ensure_rcem_table(conn)
    rows = pd.read_sql_query(
        '''
        SELECT period_month, rce_pln_mwh, rce_pln_kwh,
               corrected_rce_pln_mwh, corrected_rce_pln_kwh, source, notes
        FROM rcem_prices
        WHERE period_month = ?
        ORDER BY
            CASE source
                WHEN 'pse_official' THEN 0
                WHEN 'pse_seed' THEN 1
                WHEN 'computed_from_rce' THEN 2
                ELSE 3
            END
        ''',
        conn,
        params=(period_month,),
    )
    conn.close()

    if rows.empty and prefer != 'computed':
        seed = load_seed()
        if period_month in seed:
            entry = seed[period_month]
            mwh = entry.get('corrected_rce_pln_mwh') if use_corrected else None
            mwh = mwh or entry['rce_pln_mwh']
            return {
                'period_month': period_month,
                'rce_pln_mwh': mwh,
                'rce_pln_kwh': mwh / 1000.0,
                'source': 'pse_seed_file',
                'is_corrected': 'corrected_rce_pln_mwh' in entry and use_corrected,
            }
        if prefer == 'official':
            avg = compute_rcem_from_hourly(db_path, period_month)
            if avg is not None:
                return {
                    'period_month': period_month,
                    'rce_pln_mwh': avg,
                    'rce_pln_kwh': avg / 1000.0,
                    'source': 'computed_from_rce',
                    'is_corrected': False,
                }
        return None

    if prefer == 'computed':
        computed = rows[rows['source'] == 'computed_from_rce']
        if not computed.empty:
            rows = computed
        elif prefer == 'computed':
            avg = compute_rcem_from_hourly(db_path, period_month)
            if avg is not None:
                return {
                    'period_month': period_month,
                    'rce_pln_mwh': avg,
                    'rce_pln_kwh': avg / 1000.0,
                    'source': 'computed_from_rce',
                    'is_corrected': False,
                }

    row = rows.iloc[0]
    mwh = row['rce_pln_mwh']
    if use_corrected and pd.notna(row.get('corrected_rce_pln_mwh')):
        mwh = row['corrected_rce_pln_mwh']
    return {
        'period_month': period_month,
        'rce_pln_mwh': float(mwh),
        'rce_pln_kwh': float(mwh) / 1000.0,
        'source': row['source'],
        'is_corrected': use_corrected and pd.notna(row.get('corrected_rce_pln_mwh')),
    }


def list_rcem(db_path: str = DEFAULT_DB) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    ensure_rcem_table(conn)
    df = pd.read_sql_query(
        'SELECT * FROM rcem_prices ORDER BY period_month',
        conn,
    )
    conn.close()
    return df
