"""
Ręczne notatki pogodowe (AccuWeather / Meteoblue / obserwacja użytkownika).

Tabela: weather_notes w data/energy_model.db
To paliwo pod audyt jakości wejść — NIE cechy modelu RF.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Any

import pandas as pd

DEFAULT_DB = os.getenv('DATABASE_PATH', 'data/energy_model.db')

NOTE_KINDS = ('daily_summary', 'observation', 'forecast_tomorrow')
SOURCES = (
    'AccuWeather',
    'Meteoblue',
    'user_observation',
    'IMGW',
    'other',
)


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB
    if not os.path.isabs(path):
        # resolve relative to project root when cwd varies
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cand = os.path.join(root, path)
        if os.path.exists(cand) or not os.path.exists(path):
            path = cand
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table(db_path: str | None = None) -> None:
    conn = _connect(db_path)
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS weather_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_day TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            source TEXT NOT NULL,
            note_kind TEXT NOT NULL DEFAULT 'daily_summary',
            cloud_cover_pct REAL,
            uv_index REAL,
            brightness_index REAL,
            wind_dir TEXT,
            wind_kmh REAL,
            wind_gust_kmh REAL,
            precip_prob_pct REAL,
            thunder_prob_pct REAL,
            precip_mm REAL,
            rain_mm REAL,
            precip_duration_h REAL,
            rain_duration_h REAL,
            note_text TEXT,
            UNIQUE(note_day, source, note_kind, recorded_at)
        )
        '''
    )
    conn.commit()
    conn.close()


def insert_note(
    *,
    note_day: str,
    source: str,
    note_kind: str = 'daily_summary',
    recorded_at: str | None = None,
    cloud_cover_pct: float | None = None,
    uv_index: float | None = None,
    brightness_index: float | None = None,
    wind_dir: str | None = None,
    wind_kmh: float | None = None,
    wind_gust_kmh: float | None = None,
    precip_prob_pct: float | None = None,
    thunder_prob_pct: float | None = None,
    precip_mm: float | None = None,
    rain_mm: float | None = None,
    precip_duration_h: float | None = None,
    rain_duration_h: float | None = None,
    note_text: str | None = None,
    db_path: str | None = None,
) -> int:
    ensure_table(db_path)
    recorded_at = recorded_at or datetime.now().replace(microsecond=0).isoformat()
    conn = _connect(db_path)
    cur = conn.execute(
        '''
        INSERT INTO weather_notes (
            note_day, recorded_at, source, note_kind,
            cloud_cover_pct, uv_index, brightness_index,
            wind_dir, wind_kmh, wind_gust_kmh,
            precip_prob_pct, thunder_prob_pct,
            precip_mm, rain_mm, precip_duration_h, rain_duration_h,
            note_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            note_day,
            recorded_at,
            source,
            note_kind,
            cloud_cover_pct,
            uv_index,
            brightness_index,
            wind_dir or None,
            wind_kmh,
            wind_gust_kmh,
            precip_prob_pct,
            thunder_prob_pct,
            precip_mm,
            rain_mm,
            precip_duration_h,
            rain_duration_h,
            note_text,
        ),
    )
    conn.commit()
    row_id = int(cur.lastrowid)
    conn.close()
    return row_id


def list_notes(
    *,
    limit: int = 30,
    note_day: str | None = None,
    db_path: str | None = None,
) -> pd.DataFrame:
    ensure_table(db_path)
    conn = _connect(db_path)
    if note_day:
        df = pd.read_sql_query(
            '''
            SELECT * FROM weather_notes
            WHERE note_day = ?
            ORDER BY recorded_at DESC
            ''',
            conn,
            params=(note_day,),
        )
    else:
        df = pd.read_sql_query(
            '''
            SELECT * FROM weather_notes
            ORDER BY recorded_at DESC
            LIMIT ?
            ''',
            conn,
            params=(limit,),
        )
    conn.close()
    return df


def load_forecast_validation(csv_path: str | None = None) -> pd.DataFrame:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = csv_path or os.path.join(
        root, 'data', 'processed', 'forecasts', 'forecast_validation.csv'
    )
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path)


def validation_summary(df: pd.DataFrame | None = None) -> dict[str, Any]:
    df = load_forecast_validation() if df is None else df
    if df.empty:
        return {}
    out: dict[str, Any] = {'n_days': len(df)}
    if 'actual_pv_total' in df.columns and 'predicted_daily_raw' in df.columns:
        sub = df.dropna(subset=['actual_pv_total', 'predicted_daily_raw'])
        if not sub.empty:
            err = (sub['predicted_daily_raw'] - sub['actual_pv_total']).abs()
            out['mae_raw_5'] = float(err.mean())
    if 'actual_pv_total' in df.columns and 'predicted_midday_raw' in df.columns:
        sub = df.dropna(subset=['actual_pv_total', 'predicted_midday_raw'])
        if not sub.empty:
            err = (sub['predicted_midday_raw'] - sub['actual_pv_total']).abs()
            out['mae_raw_12'] = float(err.mean())
    return out
