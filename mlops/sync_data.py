#!/usr/bin/env python3
"""
Synchronizacja brakujących danych: pogoda (Open-Meteo) + FoxESS.

Wykrywa luki w bazie i pobiera brakujące zakresy przez API.

Użycie (macOS: poza venv nie ma `python`):
    ./venv/bin/python mlops/sync_data.py              # pogoda + FoxESS
    ./venv/bin/python mlops/sync_data.py --weather    # tylko pogoda (historia + prognoza)
    ./venv/bin/python mlops/sync_data.py --foxess     # tylko FoxESS
    ./venv/bin/python mlops/sync_data.py --dry-run    # pokaż luki bez pobierania
    ./venv/bin/python mlops/sync_data.py --csv        # FoxESS + kopie CSV w data/raw/
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _max_date(conn: sqlite3.Connection, table: str, col: str = 'timestamp') -> str | None:
    row = conn.execute(
        f"SELECT MAX(date({col})) FROM {table}"
    ).fetchone()
    return row[0] if row and row[0] else None


def foxess_day_coverage(day: str | None = None) -> dict:
    """Sprawdza kompletność danych FoxESS dla danego dnia."""
    target = day or date.today().isoformat()
    info = {
        'day': target,
        'last_timestamp': None,
        'last_hour': None,
        'row_count': 0,
        'incomplete': True,
        'age_hours': None,
    }
    if not os.path.exists(DB_PATH):
        return info

    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        '''
        SELECT MAX(timestamp), COUNT(*)
        FROM foxess_data
        WHERE date(timestamp) = ?
        ''',
        (target,),
    ).fetchone()
    conn.close()

    if not row or not row[0]:
        return info

    last_ts = row[0]
    info['last_timestamp'] = last_ts
    info['row_count'] = int(row[1] or 0)
    last_dt = datetime.fromisoformat(str(last_ts).replace(' ', 'T')[:19])
    info['last_hour'] = last_dt.hour
    now = datetime.now()
    info['age_hours'] = round((now - last_dt).total_seconds() / 3600, 2)

    if target == date.today().isoformat():
        # W ciągu dnia: niepełne, gdy ostatnia próbka jest wyraźnie stara.
        info['incomplete'] = info['age_hours'] > 2.0 and now.hour >= 10
    else:
        # Dzień zamknięty: oczekujemy danych co najmniej do ~20:00.
        info['incomplete'] = info['last_hour'] < 20

    return info


def detect_gaps() -> dict:
    today = date.today().isoformat()
    gaps = {
        'weather_history': None,
        'foxess': None,
        'today': today,
    }

    if not os.path.exists(DB_PATH):
        gaps['weather_history'] = ('2025-04-21', today)
        gaps['foxess'] = ('2025-05-01', today)
        return gaps

    conn = sqlite3.connect(DB_PATH)
    weather_max = _max_date(conn, 'weather_data')
    foxess_max = _max_date(conn, 'foxess_data')

    if weather_max and weather_max < today:
        start = (date.fromisoformat(weather_max) + timedelta(days=1)).isoformat()
        gaps['weather_history'] = (start, today)

    if foxess_max and foxess_max < today:
        start = (date.fromisoformat(foxess_max) + timedelta(days=1)).isoformat()
        gaps['foxess'] = (start, today)
    elif not foxess_max:
        gaps['foxess'] = ('2025-05-01', today)

    coverage = foxess_day_coverage(today)
    gaps['foxess_today_coverage'] = coverage
    if coverage['incomplete']:
        gaps['foxess_today_stale'] = True

    conn.close()
    return gaps


def sync_weather(dry_run: bool = False) -> None:
    gaps = detect_gaps()
    print('\n🌤️  Pogoda (Open-Meteo)')
    if gaps['weather_history']:
        start, end = gaps['weather_history']
        print(f'   Luka historii: {start} → {end}')
        if not dry_run:
            os.environ.setdefault('WEATHER_START_DATE', start)
            os.environ.setdefault('WEATHER_END_DATE', end)
    else:
        print('   Historia: aktualna ✅')

    forecast_days = int(os.getenv('WEATHER_FORECAST_DAYS', '3'))
    print(f'   Prognoza: odświeżanie Open-Meteo ({forecast_days} dni, w tym dziś)')

    if dry_run:
        return

    os.environ.setdefault('WEATHER_FORECAST_DAYS', str(forecast_days))
    subprocess.run(
        [sys.executable, os.path.join(ROOT, 'scripts/analysis/fetch_weather.py')],
        cwd=ROOT,
        check=False,
        env=os.environ.copy(),
    )


def _merge_date_ranges(ranges: list[tuple[str, str]]) -> list[tuple[str, str]]:
    if not ranges:
        return []
    parsed = sorted(
        (date.fromisoformat(start), date.fromisoformat(end))
        for start, end in ranges
    )
    merged: list[list[date]] = [[parsed[0][0], parsed[0][1]]]
    for start, end in parsed[1:]:
        if start <= merged[-1][1] + timedelta(days=1):
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(a.isoformat(), b.isoformat()) for a, b in merged]


def foxess_sync_ranges(refresh_today: bool = True) -> list[tuple[str, str]]:
    """Zakresy do pobrania: luki historyczne + opcjonalnie dziś (odświeżenie w trakcie dnia)."""
    gaps = detect_gaps()
    ranges: list[tuple[str, str]] = []
    if gaps['foxess']:
        ranges.append(gaps['foxess'])
    if refresh_today:
        ranges.append((gaps['today'], gaps['today']))
    return _merge_date_ranges(ranges)


def foxess_sync_disabled() -> bool:
    """Pauza sync FoxESS (np. po 40402) — pogoda/prognoza działają bez API Fox."""
    return os.getenv('FOXESS_SYNC_DISABLED', '').strip().lower() in ('1', 'true', 'yes', 'on')


def sync_foxess(
    dry_run: bool = False,
    refresh_today: bool = True,
    save_csv: bool | None = None,
    extra_days: list[str] | None = None,
    require_complete_today: bool = False,
) -> bool:
    if foxess_sync_disabled():
        print('\n🔋 FoxESS')
        print(
            '   ⏸️  FOXESS_SYNC_DISABLED=1 — pomijam wywołania API '
            '(odczekaj ~24h limitu; użyj plant CSV / --skip-sync).'
        )
        return True
    if save_csv is None:
        save_csv = os.getenv('FOXESS_SAVE_CSV', '').lower() in ('1', 'true', 'yes')
    ranges = foxess_sync_ranges(refresh_today=refresh_today)
    for day in extra_days or []:
        ranges.append((day, day))
    ranges = _merge_date_ranges(ranges)
    print('\n🔋 FoxESS')
    if not ranges:
        print('   Brak zakresów do pobrania')
        return True

    coverage = foxess_day_coverage()
    if coverage['incomplete'] and coverage['last_timestamp']:
        print(
            f'   ⚠️  Dziś niepełne: ostatnia próbka {coverage["last_timestamp"]} '
            f'({coverage["row_count"]} wierszy foxess_data)'
        )

    for start, end in ranges:
        if start == end:
            print(f'   Zakres: {start}')
        else:
            print(f'   Zakres: {start} → {end}')
    if dry_run:
        return True

    ok = True
    for start, end in ranges:
        cmd = [
            sys.executable,
            os.path.join(ROOT, 'src/data/foxess_fetch_all.py'),
            '--from', start,
            '--to', end,
        ]
        if not save_csv:
            cmd.append('--no-csv')
        result = subprocess.run(cmd, cwd=ROOT, check=False, env=os.environ.copy())
        if result.returncode != 0:
            print('   ❌ Pobieranie FoxESS nie powiodło się — sprawdź FOXESS_API_KEY w .env')
            ok = False
            break

    after = foxess_day_coverage()
    if ok and require_complete_today and after['incomplete']:
        if after['last_timestamp']:
            print(
                f'   ⚠️  Po sync dziś wciąż niepełne: ostatnia próbka {after["last_timestamp"]}'
            )
        else:
            print('   ⚠️  Po sync brak danych FoxESS na dziś w foxess_data')
        ok = False
    return ok


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Synchronizuj dane pogodowe i FoxESS')
    parser.add_argument('--weather', action='store_true', help='Tylko pogoda')
    parser.add_argument('--foxess', action='store_true', help='Tylko FoxESS')
    parser.add_argument(
        '--no-refresh-today',
        action='store_true',
        help='FoxESS: nie odświeżaj bieżącego dnia (tylko luki historyczne)',
    )
    parser.add_argument('--dry-run', action='store_true', help='Pokaż luki bez pobierania')
    parser.add_argument(
        '--no-csv',
        action='store_true',
        help='FoxESS: tylko baza SQLite (bez data/raw/foxess_*.csv)',
    )
    parser.add_argument(
        '--csv',
        action='store_true',
        help='FoxESS: wymuś zapis CSV (domyślnie sync bez CSV)',
    )
    args = parser.parse_args()

    do_weather = args.weather or (not args.weather and not args.foxess)
    do_foxess = args.foxess or (not args.weather and not args.foxess)
    refresh_today = not args.no_refresh_today
    foxess_save_csv = True if args.csv else (False if args.no_csv else None)

    print('=' * 70)
    print('SYNCHRONIZACJA DANYCH')
    print(f'Baza: {DB_PATH}')
    print('=' * 70)

    gaps = detect_gaps()
    print(f'Dziś: {gaps["today"]}')
    if gaps['weather_history']:
        print(f'Luka pogody (historia): {gaps["weather_history"][0]} → {gaps["weather_history"][1]}')
    if gaps['foxess']:
        print(f'Luka FoxESS: {gaps["foxess"][0]} → {gaps["foxess"][1]}')
    if do_foxess and refresh_today:
        print(f'FoxESS dziś: odświeżenie włączone ({gaps["today"]})')
    cov = gaps.get('foxess_today_coverage') or {}
    if cov.get('incomplete') and cov.get('last_timestamp'):
        print(
            f'FoxESS dziś niepełne: ostatnia próbka {cov["last_timestamp"]} '
            f'({cov["row_count"]} wierszy)'
        )

    foxess_ok = True
    if do_weather:
        sync_weather(dry_run=args.dry_run)
    if do_foxess:
        foxess_ok = sync_foxess(
            dry_run=args.dry_run,
            refresh_today=refresh_today,
            save_csv=foxess_save_csv,
        )

    if args.dry_run:
        return

    if do_foxess and not foxess_ok:
        print('\n❌ Synchronizacja FoxESS nie powiodła się.')
        sys.exit(1)

    print('\n✅ Synchronizacja zakończona.')
    print('   Następny krok: ./venv/bin/python mlops/forecast_pv.py')


if __name__ == '__main__':
    main()
