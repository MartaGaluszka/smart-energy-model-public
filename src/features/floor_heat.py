"""Cykle bufora / podłogówki z próbek Fox `load_power_kw`.

Sygnatura z nocy 16→17.10 i wieczora 17.10: plateau około 2,3–3,6 kW
przez co najmniej kilka minut, start z cichego domu (~0,2 kW).
Krótki pik powyżej 3,9 kW (czajnik, wiertarka) i zmywarka ~2,1 kW odpadają.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

ENTRY_KW = 2.3
MAX_KW = 3.75
QUIET_KW = 1.2
MIN_MINUTES = 8.0
MIN_SAMPLES_IN_BAND = 2
RAMP_MINUTES = 20.0


@dataclass(frozen=True)
class FloorHeatCycle:
    started_at: datetime
    ended_at: datetime
    kwh: float
    peak_kw: float
    ongoing: bool


def detect_floor_heat_cycles(samples: list[tuple[datetime, float]]) -> list[FloorHeatCycle]:
    """Zwraca domknięte i trwający cykl. Próbki muszą być po czasie."""
    ordered = [(t, float(p)) for t, p in samples if p is not None]
    ordered.sort(key=lambda row: row[0])
    found: list[FloorHeatCycle] = []
    index = 0
    while index < len(ordered):
        if ordered[index][1] < ENTRY_KW or ordered[index][1] > MAX_KW:
            index += 1
            continue
        start = _ramp_start(ordered, index)
        end, abort = _cycle_end(ordered, index)
        window = ordered[start:end + 1]
        in_band = sum(1 for _, power in window if power >= ENTRY_KW)
        minutes = (window[-1][0] - window[0][0]).total_seconds() / 60
        peak = max(power for _, power in window)
        ongoing = end == len(ordered) - 1 and ordered[end][1] >= ENTRY_KW
        if not abort and in_band >= MIN_SAMPLES_IN_BAND and minutes >= MIN_MINUTES and peak <= MAX_KW:
            baseline = _baseline(ordered, start)
            hours = max(minutes, 0) / 60
            net = max(0.0, _integrate(window) - baseline * hours)
            found.append(
                FloorHeatCycle(
                    started_at=window[0][0],
                    ended_at=window[-1][0],
                    kwh=round(net, 2),
                    peak_kw=round(peak, 2),
                    ongoing=ongoing,
                )
            )
        index = end + 1
    return found


def refresh_floor_heat(db_path: str, start_day: str, end_day: str) -> dict:
    """Przelicza cykle dla dni [start, end] i zapisuje je w `floor_heat_cycles`.

    Kolejne kliknięcie „Pobierz dane Fox” nadpisuje te dni, więc trwający
    cykl dostaje nowe kWh zamiast drugiego wiersza.
    """
    conn = sqlite3.connect(db_path)
    try:
        if not _has_foxess_data(conn):
            return {'days': [], 'kwh': 0.0, 'cycles': 0}
        _ensure_table(conn)
        start = datetime.fromisoformat(start_day).date()
        end = datetime.fromisoformat(end_day).date()
        day = start
        stored: list[tuple[str, float, int]] = []
        while day <= end:
            iso = day.isoformat()
            rows = conn.execute(
                '''
                SELECT timestamp, load_power_kw
                FROM foxess_data
                WHERE DATE(timestamp) = ? AND load_power_kw IS NOT NULL
                ORDER BY timestamp
                ''',
                (iso,),
            ).fetchall()
            samples = []
            for raw_ts, power in rows:
                stamp = datetime.fromisoformat(str(raw_ts).replace(' ', 'T')[:19])
                samples.append((stamp, float(power)))
            cycles = detect_floor_heat_cycles(samples)
            conn.execute('DELETE FROM floor_heat_cycles WHERE day = ?', (iso,))
            for cycle in cycles:
                conn.execute(
                    '''
                    INSERT INTO floor_heat_cycles
                        (started_at, ended_at, day, kwh, peak_kw, ongoing)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        cycle.started_at.strftime('%Y-%m-%d %H:%M:%S'),
                        cycle.ended_at.strftime('%Y-%m-%d %H:%M:%S'),
                        iso,
                        cycle.kwh,
                        cycle.peak_kw,
                        1 if cycle.ongoing else 0,
                    ),
                )
            night = conn.execute(
                '''
                SELECT COALESCE(SUM(kwh), 0)
                FROM floor_heat_cycles
                WHERE day = ? AND CAST(substr(started_at, 12, 2) AS INTEGER) < 10
                ''',
                (iso,),
            ).fetchone()
            stored.append(
                (iso, round(sum(c.kwh for c in cycles), 2), len(cycles), round(float(night[0] or 0), 2))
            )
            day += timedelta(days=1)
        conn.commit()
    finally:
        conn.close()
    present = [row for row in stored if row[2] > 0]
    return {
        'days': [
            {'day': day, 'kwh': kwh, 'cycles': n, 'night_kwh': night_kwh}
            for day, kwh, n, night_kwh in present
        ],
        'kwh': round(sum(kwh for _, kwh, _, _ in present), 2),
        'cycles': sum(n for _, _, n, _ in present),
    }


def floor_heat_message(summary: dict) -> str:
    days = summary.get('days') or []
    if not days:
        return ''
    parts = [
        f"{_pl_day(row['day'])}: {_pl_kwh(row['kwh'])} kWh ({row['cycles']} cykli)"
        for row in days
    ]
    return 'Podłoga ' + ', '.join(parts) + '.'


def _pl_day(iso: str) -> str:
    year, month, day = iso.split('-')
    return f'{int(day):02d}.{month}'


def _pl_kwh(value: float) -> str:
    return f'{value:.1f}'.replace('.', ',')


def _has_foxess_data(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'foxess_data'"
    ).fetchone()
    return row is not None


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS floor_heat_cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL UNIQUE,
            ended_at TEXT NOT NULL,
            day TEXT NOT NULL,
            kwh REAL NOT NULL,
            peak_kw REAL NOT NULL,
            ongoing INTEGER NOT NULL DEFAULT 0
        )
        '''
    )
    conn.execute(
        'CREATE INDEX IF NOT EXISTS idx_floor_heat_cycles_day ON floor_heat_cycles(day)'
    )


def _ramp_start(samples: list[tuple[datetime, float]], index: int) -> int:
    start = index
    cursor = index - 1
    while cursor >= 0:
        stamp, power = samples[cursor]
        if power > MAX_KW or power < QUIET_KW:
            break
        if (samples[index][0] - stamp).total_seconds() > RAMP_MINUTES * 60:
            break
        start = cursor
        cursor -= 1
    return start


def _cycle_end(samples: list[tuple[datetime, float]], index: int) -> tuple[int, bool]:
    end = index
    cursor = index
    while cursor < len(samples):
        _, power = samples[cursor]
        if power > MAX_KW:
            return end, True
        if power < QUIET_KW and cursor > index:
            return end, False
        end = cursor
        cursor += 1
    return end, False


def _baseline(samples: list[tuple[datetime, float]], start: int) -> float:
    if start > 0 and samples[start - 1][1] < QUIET_KW:
        return samples[start - 1][1]
    return 0.2


def _integrate(samples: list[tuple[datetime, float]]) -> float:
    total = 0.0
    for (t0, p0), (t1, p1) in zip(samples, samples[1:]):
        hours = (t1 - t0).total_seconds() / 3600
        if 0 < hours < 0.3:
            total += (p0 + p1) / 2 * hours
    return total
