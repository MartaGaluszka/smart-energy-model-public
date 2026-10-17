"""Dzień licznika i strefa G12w liczone bez skanu date() — ta sama matematyka co dotychczas."""

from __future__ import annotations

import sqlite3

import pandas as pd

from api.services.bill_simulator import _load_counter_rows, _slice_days, _sqlite_utc_day, _zones
from src.optimization.g12w_tariff import classify_zone


def _sqlite_date(value: str) -> str:
    conn = sqlite3.connect(':memory:')
    try:
        return conn.execute('SELECT date(?)', (value,)).fetchone()[0]
    finally:
        conn.close()


def test_utc_day_matches_sqlite_date_for_offsets_and_naive_clocks():
    samples = [
        '2025-06-01 00:30:00+02:00',
        '2025-06-01 02:00:00+02:00',
        '2025-06-01 12:00:00+02:00',
        '2025-01-15 00:30:00+01:00',
        '2025-01-15 01:30:00+01:00',
        '2025-06-01 12:00:00',
        '2025-06-01T12:00:00+02:00',
        '2025-06-01 23:30:00-02:00',
    ]
    got = _sqlite_utc_day(pd.Series(samples))
    assert list(got) == [_sqlite_date(sample) for sample in samples]


def test_utc_day_of_an_empty_series_stays_empty():
    assert list(_sqlite_utc_day(pd.Series(dtype=str))) == []


def test_zones_match_classify_zone_across_a_holiday_week():
    hours = pd.Series(pd.date_range('2026-01-01', '2026-01-08', freq='h', inclusive='left'))
    got = _zones(hours)
    expected = [classify_zone(stamp.to_pydatetime()) for stamp in hours]
    assert list(got) == expected


def test_zones_of_an_empty_clock_stays_empty():
    assert len(_zones(pd.to_datetime([]))) == 0


def test_slice_days_keeps_only_the_segment_and_accepts_nothing():
    series = pd.Series({'2025-06-30': 1.0, '2025-07-01': 2.0, '2025-07-02': 3.0})
    cut = _slice_days(series, '2025-07-01', '2025-07-01')
    assert list(cut.index) == ['2025-07-01']
    assert float(cut.iloc[0]) == 2.0
    assert _slice_days(None, '2025-07-01', '2025-07-01').empty
    assert _slice_days(pd.Series(dtype=float), '2025-07-01', '2025-07-01').empty


def _counter_db() -> sqlite3.Connection:
    conn = sqlite3.connect(':memory:')
    conn.execute(
        '''
        CREATE TABLE foxess_timeseries (
            timestamp TEXT NOT NULL,
            variable TEXT NOT NULL,
            value REAL
        )
        '''
    )
    conn.executemany(
        'INSERT INTO foxess_timeseries (timestamp, variable, value) VALUES (?, ?, ?)',
        [
            ('2025-06-01 00:30:00+02:00', 'gridConsumption', 1.0),
            ('2025-06-01 03:00:00+02:00', 'gridConsumption', 2.0),
            ('2025-06-02 12:00:00', 'gridConsumption', 3.0),
            ('2025-06-03 12:00:00+02:00', 'feedin', 9.0),
        ],
    )
    conn.commit()
    return conn


def test_counter_rows_drop_the_utc_day_outside_the_window_without_an_index():
    conn = _counter_db()
    try:
        frame = _load_counter_rows(conn, 'gridConsumption', '2025-06-01', '2025-06-02')
    finally:
        conn.close()

    assert list(frame['day']) == ['2025-06-01', '2025-06-02']
    assert list(frame['value']) == [2.0, 3.0]


def test_counter_rows_use_the_covering_index_when_it_exists():
    conn = _counter_db()
    try:
        conn.execute(
            '''
            CREATE INDEX idx_foxess_ts_grid_consumption
            ON foxess_timeseries(timestamp, value) WHERE variable = 'gridConsumption'
            '''
        )
        frame = _load_counter_rows(conn, 'gridConsumption', '2025-06-01', '2025-06-01')
    finally:
        conn.close()

    assert list(frame['day']) == ['2025-06-01']
    assert float(frame['value'].iloc[0]) == 2.0
