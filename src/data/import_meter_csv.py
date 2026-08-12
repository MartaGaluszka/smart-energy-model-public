"""
Import godzinowych odczytów licznika z eksportu CSV portalu Tauron.

Format: Data; Strefa; Wartość kWh; Rodzaj;
Rodzaj: „pobrana po zbilansowaniu” / „oddana po zbilansowaniu”
Strefa: T1 (szczyt), T2 (pozaszczyt)
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

METER_HOURLY_DDL = '''
CREATE TABLE IF NOT EXISTS meter_hourly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    zone VARCHAR(2) NOT NULL,
    flow VARCHAR(10) NOT NULL,
    kwh REAL NOT NULL,
    source VARCHAR(50) DEFAULT 'licznik_tauron_csv',
    UNIQUE(timestamp, zone, flow, source)
);
CREATE INDEX IF NOT EXISTS idx_meter_hourly_ts ON meter_hourly(timestamp);
'''


def _parse_datetime(data_str: str) -> str:
    """'2025-05-01 13:00' lub '2025-05-01 24:00' → timestamp ISO."""
    m = re.match(r'(\d{4}-\d{2}-\d{2})\s+(\d{1,2}):00', data_str.strip())
    if not m:
        raise ValueError(f'Nieznany format daty: {data_str!r}')
    day, hour = m.group(1), int(m.group(2))
    if hour == 24:
        # Godzina 24:00 w eksporcie Tauron = koniec doby → 00:00 następnego dnia
        # (nie 23:00 — kolidowałoby z osobnym wierszem 23:00)
        next_day = (pd.Timestamp(day) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        return f'{next_day} 00:00:00'
    return f'{day} {hour:02d}:00:00'


def _flow_type(rodzaj: str) -> str:
    r = (rodzaj or '').strip().lower()
    if 'pobran' in r:
        return 'import'
    if 'oddan' in r:
        return 'export'
    raise ValueError(f'Nieznany rodzaj: {rodzaj!r}')


def read_meter_csv(path: str | Path) -> pd.DataFrame:
    """Wczytuje i normalizuje CSV licznika."""
    df = pd.read_csv(
        path,
        sep=';',
        encoding='utf-8',
        dtype=str,
    )
    df.columns = [c.strip() for c in df.columns]

    required = {'Data', 'Strefa', 'Wartość kWh', 'Rodzaj'}
    if not required.issubset(df.columns):
        raise ValueError(f'Brak kolumn w CSV. Oczekiwano {required}, jest {set(df.columns)}')

    out = pd.DataFrame()
    out['reading_day'] = df['Data'].str.strip().str[:10]
    out['timestamp'] = df['Data'].map(_parse_datetime)
    out['zone'] = df['Strefa'].str.strip().str.upper()
    out['kwh'] = df['Wartość kWh'].str.replace(',', '.', regex=False).astype(float)
    out['flow'] = df['Rodzaj'].map(_flow_type)
    out['source'] = 'licznik_tauron_csv'
    return out


def ensure_meter_hourly_table(conn: sqlite3.Connection) -> None:
    conn.executescript(METER_HOURLY_DDL)
    conn.commit()


def save_meter_hourly(df: pd.DataFrame, db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    ensure_meter_hourly_table(conn)
    rows = 0
    for _, r in df.iterrows():
        conn.execute(
            '''
            INSERT OR REPLACE INTO meter_hourly (timestamp, zone, flow, kwh, source)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (r['timestamp'], r['zone'], r['flow'], r['kwh'], r['source']),
        )
        rows += 1
    conn.commit()
    conn.close()
    return rows


def aggregate_period(
    df: pd.DataFrame,
    period_start: str,
    period_end: str,
) -> dict:
    """Sumy kWh za okres — po dacie z kolumny Data (godz. 24:00 = ten sam dzień rozliczeniowy)."""
    days = df['reading_day'] if 'reading_day' in df.columns else df['timestamp'].str[:10]
    mask = (days >= period_start) & (days <= period_end)
    sub = df.loc[mask]

    def _sum(flow: str, zone: Optional[str] = None) -> float:
        m = sub['flow'] == flow
        if zone:
            m &= sub['zone'] == zone
        return round(sub.loc[m, 'kwh'].sum(), 3)

    return {
        'period_start': period_start,
        'period_end': period_end,
        'import_kwh': _sum('import'),
        'export_kwh': _sum('export'),
        'import_zone1_kwh': _sum('import', 'T1'),
        'import_zone2_kwh': _sum('import', 'T2'),
        'export_zone1_kwh': _sum('export', 'T1'),
        'export_zone2_kwh': _sum('export', 'T2'),
    }


METER_READINGS_DDL = '''
CREATE TABLE IF NOT EXISTS meter_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    import_kwh REAL,
    export_kwh REAL,
    import_zone1_kwh REAL,
    import_zone2_kwh REAL,
    export_zone1_kwh REAL,
    export_zone2_kwh REAL,
    source VARCHAR(50) DEFAULT 'licznik_tauron',
    notes TEXT,
    UNIQUE(period_start, period_end, source)
);
'''


def upsert_meter_reading(summary: dict, db_path: str, notes: str = '') -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(METER_READINGS_DDL)
    conn.execute(
        '''
        INSERT OR REPLACE INTO meter_readings (
            period_start, period_end, import_kwh, export_kwh,
            import_zone1_kwh, import_zone2_kwh, export_zone1_kwh, export_zone2_kwh,
            source, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            summary['period_start'], summary['period_end'],
            summary['import_kwh'], summary['export_kwh'],
            summary['import_zone1_kwh'], summary['import_zone2_kwh'],
            summary['export_zone1_kwh'], summary['export_zone2_kwh'],
            'licznik_tauron_csv', notes,
        ),
    )
    conn.commit()
    conn.close()


def _period_bounds(df: pd.DataFrame) -> Tuple[str, str]:
    if 'reading_day' in df.columns:
        days = df['reading_day']
    else:
        days = df['timestamp'].str[:10]
    return str(days.min()), str(days.max())


def import_meter_csv(
    *paths: str | Path,
    db_path: str = 'data/energy_model.db',
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Tuple[pd.DataFrame, dict]:
    """
    Import jednego lub wielu CSV (np. osobno pobór i oddanie z portalu).
    """
    if not paths:
        raise ValueError('Podaj co najmniej jedną ścieżkę CSV')

    frames = [read_meter_csv(p) for p in paths]
    df = pd.concat(frames, ignore_index=True)
    n = save_meter_hourly(df, db_path)

    if period_start is None or period_end is None:
        period_start, period_end = _period_bounds(df)

    summary = aggregate_period(df, period_start, period_end)
    notes = f'Import CSV licznika | {n} wierszy godzinowych | {len(paths)} plik(ów)'
    upsert_meter_reading(summary, db_path, notes)
    return df, summary
