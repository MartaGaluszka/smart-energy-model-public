#!/usr/bin/env python3
"""Odświeżenie SoC z Fox Cloud tuż przed decyzją B2 (21:15 plan, 22:00 apply, 4:00 top-up).

Dlaczego: advisor czyta SoC z ``foxess_data``. Gdy ostatni zapis jest starszy niż
``BATTERY_SOC_MAX_AGE_HOURS`` (domyślnie 0,75 h), reguła nocna nie ma stanu baterii
i pomija ForceCharge (case 09.11.2026: 57% z 18:50 vs ~14% o 22:00).

Zasady (``foxess-db-first-quota``):
- jedno wąskie pobranie: tylko dzisiejszy dzień, bez CSV;
- respektuje pauzę (``is_api_paused``) — wtedy nic nie wołamy;
- pomija pobranie, gdy odczyt jest świeży (``--max-age-min``);
- nigdy nie przerywa wywołującego skryptu (exit 0), błąd tylko w logu.

Użycie:
    ./venv/bin/python mlops/refresh_battery_soc.py [--max-age-min 10] [--force]
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, '.env'))

DB_PATH = os.getenv('DATABASE_PATH', os.path.join(ROOT, 'data/energy_model.db'))
FETCH_TIMEOUT_S = 180


def latest_reading() -> tuple[datetime | None, float | None]:
    """Ostatni zapis z ``foxess_data``: (timestamp, SoC %)."""
    if not os.path.exists(DB_PATH):
        return None, None
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    try:
        row = conn.execute(
            'SELECT timestamp, battery_soc_percent FROM foxess_data '
            'WHERE battery_soc_percent IS NOT NULL ORDER BY timestamp DESC LIMIT 1'
        ).fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        return None, None
    ts = datetime.fromisoformat(str(row[0]).replace(' ', 'T')[:19])
    return ts, row[1]


def age_minutes(ts: datetime | None, now: datetime | None = None) -> float | None:
    if ts is None:
        return None
    return ((now or datetime.now()) - ts).total_seconds() / 60.0


def describe(ts: datetime | None, soc: float | None) -> str:
    age = age_minutes(ts)
    if ts is None or age is None:
        return 'brak odczytu w foxess_data'
    soc_txt = f'{soc:.0f}%' if soc is not None else '?'
    return f'SoC {soc_txt} @ {ts:%H:%M:%S} ({age:.0f} min temu)'


def main() -> int:
    parser = argparse.ArgumentParser(description='Odśwież SoC z Fox przed decyzją B2')
    parser.add_argument(
        '--max-age-min',
        type=float,
        default=10.0,
        help='Nie pobieraj, gdy ostatni odczyt jest młodszy niż tyle minut (domyślnie 10)',
    )
    parser.add_argument('--force', action='store_true', help='Pobierz mimo świeżego odczytu')
    args = parser.parse_args()

    before_ts, before_soc = latest_reading()
    print(f'[refresh-soc] przed: {describe(before_ts, before_soc)}')

    from src.data.foxess_api_guard import is_api_paused, pause_message

    if is_api_paused():
        print(f'[refresh-soc] ⏸️  {pause_message()} — zostaję przy bazie')
        return 0

    age = age_minutes(before_ts)
    if not args.force and age is not None and age < args.max_age_min:
        print(f'[refresh-soc] odczyt świeży (<{args.max_age_min:.0f} min) — pomijam pobranie')
        return 0

    today = date.today().isoformat()
    cmd = [
        sys.executable,
        os.path.join(ROOT, 'src/data/foxess_fetch_all.py'),
        '--from', today,
        '--to', today,
        '--no-csv',
    ]
    print(f'[refresh-soc] pobieram Fox ({today}, 1 dzień)…')
    env = os.environ.copy()
    # foxess_fetch_all importuje `src.*` — działa też przy ręcznym uruchomieniu bez _venv.sh.
    env['PYTHONPATH'] = ROOT + os.pathsep + env.get('PYTHONPATH', '')
    try:
        result = subprocess.run(
            cmd,
            cwd=ROOT,
            check=False,
            env=env,
            timeout=FETCH_TIMEOUT_S,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.TimeoutExpired:
        print(f'[refresh-soc] ⚠️  timeout {FETCH_TIMEOUT_S}s — zostaję przy bazie', file=sys.stderr)
        return 0

    if result.returncode != 0:
        tail = (result.stderr or '').strip().splitlines()[-3:]
        print(f'[refresh-soc] ⚠️  fetch kod {result.returncode}: {" | ".join(tail)}', file=sys.stderr)

    after_ts, after_soc = latest_reading()
    print(f'[refresh-soc] po: {describe(after_ts, after_soc)}')
    after_age = age_minutes(after_ts)
    if after_age is None or after_age > 45:
        print(
            '[refresh-soc] ⚠️  SoC nadal nieświeży (>45 min) — decyzja pójdzie ze starego odczytu w bazie',
            file=sys.stderr,
        )
    return 0


if __name__ == '__main__':
    sys.exit(main())
