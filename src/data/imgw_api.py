"""
Dane dobowe IMGW (klimat) — pokrywa śnieżna, opady, temperatura.

Źródło: danepubliczne.imgw.pl — pliki ZIP miesięczne (rank=klimat).
Stacja wybierana automatycznie: najbliższa sieci klimatycznej IMGW do WEATHER_LAT/LON.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import math
import os
import sqlite3
import urllib.request
import zipfile
from datetime import date, datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

SYNOP_URL = 'https://danepubliczne.imgw.pl/api/data/meteo/synop'
CLIMATE_BASE = (
    'https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/'
    'dane_meteorologiczne/dobowe/klimat'
)

# k_d_format.txt — kolejność pól w pliku k_d_MM_YYYY.csv
CLIMATE_COLUMNS = [
    'station_code', 'station_name', 'year', 'month', 'day',
    'temp_max_c', 'temp_max_status',
    'temp_min_c', 'temp_min_status',
    'temp_mean_c', 'temp_mean_status',
    'temp_ground_min_c', 'temp_ground_min_status',
    'precip_mm', 'precip_status', 'precip_type',
    'snow_depth_cm', 'snow_depth_status',
]


def _get_json(url: str, timeout: int = 120) -> list | dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _download_bytes(url: str, timeout: int = 120) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def fetch_synop_stations() -> pd.DataFrame:
    """Stacje SYNOP IMGW z współrzędnymi (do wyboru najbliższej sieci klimat)."""
    rows = _get_json(SYNOP_URL)
    df = pd.DataFrame(rows)
    df = df[df['lat'].notna() & df['lon'].notna()].copy()
    df['station_code'] = df['kod_stacji'].astype(str)
    df['station_name'] = df['nazwa_stacji'].astype(str).str.strip()
    df['lat'] = df['lat'].astype(float)
    df['lon'] = df['lon'].astype(float)
    return df[['station_code', 'station_name', 'lat', 'lon']]


def climate_month_url(year: int, month: int) -> str:
    return f'{CLIMATE_BASE}/{year}/{year}_{month:02d}_k.zip'


def _decode_climate_csv(raw: bytes) -> str:
    for enc in ('cp1250', 'utf-8', 'latin-1'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('latin-1', errors='replace')


def parse_climate_csv(raw: bytes) -> pd.DataFrame:
    """Parsuje plik k_d_MM_YYYY.csv z archiwum ZIP."""
    text = _decode_climate_csv(raw)
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = next(csv.reader([line]))
        if len(parts) < len(CLIMATE_COLUMNS):
            continue
        rows.append(dict(zip(CLIMATE_COLUMNS, parts[: len(CLIMATE_COLUMNS)])))

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df['station_name'] = df['station_name'].str.strip()
    for col in ('year', 'month', 'day'):
        df[col] = pd.to_numeric(df[col], errors='coerce')
    for col in ('temp_max_c', 'temp_min_c', 'temp_mean_c', 'temp_ground_min_c', 'precip_mm', 'snow_depth_cm'):
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['day'] = df.apply(
        lambda r: f"{int(r['year']):04d}-{int(r['month']):02d}-{int(r['day']):02d}"
        if pd.notna(r['year']) and pd.notna(r['month']) and pd.notna(r['day'])
        else None,
        axis=1,
    )
    # status 8 = brak pomiaru, 9 = brak zjawiska; pusty status = pomiar OK (w tym 0 cm)
    missing_snow = df['snow_depth_status'].isin(['8', '9'])
    df.loc[missing_snow, 'snow_depth_cm'] = None
    missing_precip = df['precip_status'].isin(['8', '9'])
    df.loc[missing_precip, 'precip_mm'] = None
    return df


def download_climate_month(year: int, month: int) -> pd.DataFrame:
    url = climate_month_url(year, month)
    logger.info('Pobieram IMGW klimat: %s', url)
    payload = _download_bytes(url)
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        csv_name = [n for n in zf.namelist() if n.lower().endswith('.csv')][0]
        raw = zf.read(csv_name)
    return parse_climate_csv(raw)


def _month_range(start: date, end: date) -> list[tuple[int, int]]:
    months = []
    cur = date(start.year, start.month, 1)
    end_marker = date(end.year, end.month, 1)
    while cur <= end_marker:
        months.append((cur.year, cur.month))
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return months


def resolve_climate_station(
    latitude: float,
    longitude: float,
    probe_year: int = 2025,
    probe_month: int = 12,
    station_code: Optional[str] = None,
) -> dict:
    """
    Wybiera najbliższą stację sieci klimat IMGW (z danymi w pliku miesięcznym).
    """
    if station_code:
        synop = fetch_synop_stations()
        hit = synop[synop['station_code'] == str(station_code)]
        if hit.empty:
            raise ValueError(f'Nieznany kod stacji IMGW: {station_code}')
        row = hit.iloc[0]
        return {
            'station_code': row['station_code'],
            'station_name': row['station_name'],
            'lat': row['lat'],
            'lon': row['lon'],
            'distance_km': haversine_km(latitude, longitude, row['lat'], row['lon']),
        }

    probe = download_climate_month(probe_year, probe_month)
    codes_in_climate = set(probe['station_code'].astype(str))
    synop = fetch_synop_stations()
    synop = synop[synop['station_code'].isin(codes_in_climate)].copy()
    if synop.empty:
        raise ValueError('Brak stacji klimat IMGW do dopasowania.')

    synop['distance_km'] = synop.apply(
        lambda r: haversine_km(latitude, longitude, r['lat'], r['lon']), axis=1
    )
    best = synop.sort_values('distance_km').iloc[0]
    return {
        'station_code': best['station_code'],
        'station_name': best['station_name'],
        'lat': float(best['lat']),
        'lon': float(best['lon']),
        'distance_km': float(best['distance_km']),
    }


def fetch_climate_daily(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    station_code: Optional[str] = None,
) -> tuple[pd.DataFrame, dict]:
    """Pobiera dane dobowe klimat IMGW dla najbliższej stacji."""
    station = resolve_climate_station(latitude, longitude, station_code=station_code)
    start = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()

    parts = []
    for year, month in _month_range(start, end):
        try:
            part = download_climate_month(year, month)
            parts.append(part)
        except Exception as exc:
            logger.warning('Pominięto %04d-%02d: %s', year, month, exc)

    if not parts:
        return pd.DataFrame(), station

    df = pd.concat(parts, ignore_index=True)
    code = station['station_code']
    df = df[df['station_code'].astype(str) == str(code)].copy()
    df = df[(df['day'] >= start_date) & (df['day'] <= end_date)]
    df = df.sort_values('day').reset_index(drop=True)
    return df, station


def ensure_imgw_daily_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS imgw_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day DATE NOT NULL,
            station_code VARCHAR(20) NOT NULL,
            station_name VARCHAR(100),
            station_lat REAL,
            station_lon REAL,
            distance_km REAL,
            temp_mean_c REAL,
            temp_min_c REAL,
            temp_max_c REAL,
            precip_mm REAL,
            snow_depth_cm REAL,
            snow_depth_status VARCHAR(5),
            data_source VARCHAR(50) DEFAULT 'IMGW-klimat',
            UNIQUE(day, station_code)
        )
        '''
    )
    conn.execute('CREATE INDEX IF NOT EXISTS idx_imgw_daily_day ON imgw_daily(day)')


def save_imgw_daily_to_db(
    df: pd.DataFrame,
    station: dict,
    db_path: str = 'data/energy_model.db',
) -> int:
    if df.empty:
        return 0

    conn = sqlite3.connect(db_path)
    ensure_imgw_daily_table(conn)
    rows = 0
    for _, r in df.iterrows():
        conn.execute(
            '''
            INSERT OR REPLACE INTO imgw_daily (
                day, station_code, station_name, station_lat, station_lon, distance_km,
                temp_mean_c, temp_min_c, temp_max_c, precip_mm,
                snow_depth_cm, snow_depth_status, data_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                r['day'],
                station['station_code'],
                station['station_name'],
                station.get('lat'),
                station.get('lon'),
                station.get('distance_km'),
                r.get('temp_mean_c'),
                r.get('temp_min_c'),
                r.get('temp_max_c'),
                r.get('precip_mm'),
                r.get('snow_depth_cm'),
                r.get('snow_depth_status'),
                'IMGW-klimat',
            ),
        )
        rows += 1
    conn.commit()
    conn.close()
    return rows


def load_imgw_daily(
    db_path: str,
    start_date: str,
    end_date: str,
    station_code: Optional[str] = None,
) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    query = '''
        SELECT day, station_code, station_name, distance_km,
               temp_mean_c, temp_min_c, temp_max_c,
               precip_mm, snow_depth_cm, snow_depth_status
        FROM imgw_daily
        WHERE day BETWEEN ? AND ?
    '''
    params: list = [start_date, end_date]
    if station_code:
        query += ' AND station_code = ?'
        params.append(station_code)
    query += ' ORDER BY day'
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df
