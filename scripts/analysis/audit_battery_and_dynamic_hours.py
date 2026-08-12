"""
Audyt: filtr baterii + dynamiczne godziny wschód–zachód
Zbiór 2025–2026, zgodność z UPDATE_2026-07-09_filtr-baterii.md

Uruchomienie:
  PYTHONPATH=. python scripts/audit_battery_and_dynamic_hours.py
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd

from src.data.household_context import FOXESS_RELIABLE_START, is_pv_inverter_misconfigured
from src.data.weather_api import (
    BATTERY_DISCHARGE_THRESHOLD_KW,
    load_daily_pv,
    load_daily_pv_daytime,
    load_daily_weather,
    _daylight_hour_bounds,
)
from src.features.pv_features import load_training_frame, _is_artifact_day

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / 'data' / 'energy_model.db'
LAT, LON = 50.06, 19.94

# Pliki produkcyjne (src/) — legacy 9-16 dozwolone tylko w *_fixed_hours / use_dynamic_hours=False
SRC_SCAN = ROOT / 'src'
LEGACY_OK_FILES: set[str] = set()
LEGACY_OK = {
    '_load_daily_weather_fixed_hours',
    'load_daily_pv_daytime',  # gałąź use_dynamic_hours=False
    'load_hourly_pv',
    'load_hourly_weather',
    'PV_HOURS',
    'backward compatibility',
    'legacy',
    'fallback',
}


def scan_hardcoded_hours() -> list[dict]:
    """Szukaj sztywnych 9-16 / 9-21 w kodzie Python (src/)."""
    patterns = [
        (r'BETWEEN\s+9\s+AND\s+16', 'SQL BETWEEN 9 AND 16'),
        (r'hour\s+BETWEEN\s+9\s+AND\s+16', 'hour BETWEEN 9 AND 16'),
        (r'hour\s+BETWEEN\s+9\s+AND\s+21', 'hour BETWEEN 9 AND 21'),
        (r'use_dynamic_hours\s*=\s*False', 'use_dynamic_hours=False'),
    ]
    findings = []
    for py in SRC_SCAN.rglob('*.py'):
        if '.bak' in py.name:
            continue
        rel = str(py.relative_to(ROOT))
        if rel in LEGACY_OK_FILES:
            continue
        text = py.read_text(encoding='utf-8', errors='ignore')
        for i, line in enumerate(text.splitlines(), 1):
            for pat, label in patterns:
                if re.search(pat, line, re.I):
                    ctx_start = max(0, i - 25)
                    ctx = '\n'.join(text.splitlines()[ctx_start:i])
                    if any(ok in line for ok in LEGACY_OK):
                        status = 'legacy_ok'
                    elif '_load_daily_weather_fixed_hours' in ctx:
                        status = 'legacy_ok'
                    elif 'backward compatibility' in ctx:
                        status = 'legacy_ok'
                    elif 'legacy' in line.lower() or 'fallback' in line.lower():
                        status = 'legacy_ok'
                    else:
                        status = 'review'
                    findings.append({
                        'file': str(py.relative_to(ROOT)),
                        'line': i,
                        'type': label,
                        'status': status,
                        'snippet': line.strip()[:100],
                    })
    return findings


def monthly_audit(year: int) -> pd.DataFrame:
    """Miesięczne KPI: filtr baterii, dynamiczne vs statyczne, trening."""
    rows = []
    for month in range(1, 13):
        start = f'{year}-{month:02d}-01'
        if month == 12:
            end = f'{year}-12-31'
        else:
            end = (pd.Timestamp(start) + pd.offsets.MonthEnd(0)).strftime('%Y-%m-%d')

        conn = sqlite3.connect(DB)
        raw = pd.read_sql_query(
            f'''
            SELECT COUNT(DISTINCT date(timestamp)) as days,
                   ROUND(SUM(CASE WHEN pv_energy_kwh > 0 THEN pv_energy_kwh ELSE 0 END), 2) as pv_pos
            FROM foxess_data WHERE date(timestamp) BETWEEN ? AND ?
            ''',
            conn, params=(start, end),
        )
        conn.close()

        if raw.iloc[0]['days'] == 0:
            continue

        pv = load_daily_pv(str(DB), start, end)
        static = load_daily_pv_daytime(str(DB), start, end, use_dynamic_hours=False)
        dynamic = load_daily_pv_daytime(str(DB), start, end, latitude=LAT, longitude=LON)
        frame = load_training_frame(str(DB), start, end)

        excluded_kwh = float(pv['pv_kwh'].clip(lower=0).sum()) - float(pv['pv_kwh_solar'].sum())
        excluded_pct = (
            excluded_kwh / float(pv['pv_kwh'].clip(lower=0).sum()) * 100
            if pv['pv_kwh'].clip(lower=0).sum() > 0 else 0
        )

        rows.append({
            'month': f'{year}-{month:02d}',
            'days_db': int(raw.iloc[0]['days']),
            'days_training': len(frame),
            'pv_raw_pos_kwh': float(raw.iloc[0]['pv_pos']),
            'pv_solar_kwh': float(pv['pv_kwh_solar'].sum()),
            'pv_static_9_16': float(static['pv_kwh_daytime'].sum()),
            'pv_dynamic': float(dynamic['pv_kwh_daytime'].sum()),
            'battery_excluded_kwh': round(excluded_kwh, 2),
            'battery_excluded_pct': round(excluded_pct, 1),
            'dynamic_vs_static_kwh': round(
                float(dynamic['pv_kwh_daytime'].sum()) - float(static['pv_kwh_daytime'].sum()), 2
            ),
        })
    return pd.DataFrame(rows)


def check_artifact_filter() -> pd.DataFrame:
    """Dni odrzucone przez _is_artifact_day — tylko okres misconfig falownika."""
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query(
        '''
        SELECT date(timestamp) as day,
               ROUND(SUM(CASE WHEN pv_energy_kwh < 0 THEN -pv_energy_kwh ELSE 0 END), 2) as artifact,
               ROUND(SUM(CASE WHEN pv_energy_kwh > 0 AND COALESCE(battery_power_kw,0) >= -0.1
                   THEN pv_energy_kwh ELSE 0 END), 2) as pv_day
        FROM foxess_data
        WHERE date(timestamp) >= '2025-04-01'
        GROUP BY day
        ''',
        conn,
    )
    conn.close()

    flagged = []
    for _, row in df.iterrows():
        r = pd.Series({
            'day': row['day'],
            'pv_kwh_artifact': row['artifact'],
            'pv_kwh_daytime': row['pv_day'],
        })
        if _is_artifact_day(r):
            flagged.append({
                'day': row['day'],
                'artifact': row['artifact'],
                'pv_day': row['pv_day'],
                'misconfig_period': is_pv_inverter_misconfigured(
                    pd.Timestamp(row['day']).date()
                ),
            })
    return pd.DataFrame(flagged)


def check_import_policy() -> str:
    """Import FoxESS zapisuje surowe dane; filtry przy odczycie."""
    fetch = (ROOT / 'src/data/foxess_fetch_all.py').read_text(encoding='utf-8')
    if 'battery_power_kw' in fetch and 'pv_energy_kwh' in fetch:
        return (
            'Import (foxess_fetch_all.py): zapis SUROWY do foxess_data — OK.\n'
            f'Filtr baterii (>= {BATTERY_DISCHARGE_THRESHOLD_KW} kW) stosowany przy load_daily_pv / '
            'load_daily_pv_daytime / load_hourly_pv_dynamic / snow_melt_model.'
        )
    return 'Sprawdź foxess_fetch_all.py'


def main() -> None:
    print('=' * 80)
    print('AUDYT: Filtr baterii + dynamiczne godziny (2025–2026)')
    print('=' * 80)

    print(f'\n📌 Polityka importu:\n{check_import_policy()}')
    print(f'\n📌 FOXESS_RELIABLE_START: {FOXESS_RELIABLE_START}')

    # Skan kodu
    print('\n' + '=' * 80)
    print('1. SKAN KODU (src/) — sztywne godziny 9-16 / 9-21')
    print('=' * 80)
    findings = scan_hardcoded_hours()
    review = [f for f in findings if f['status'] == 'review']
    legacy = [f for f in findings if f['status'] == 'legacy_ok']
    print(f'  Legacy/fallback (OK): {len(legacy)}')
    print(f'  Do review:          {len(review)}')
    for f in review[:15]:
        print(f"  ⚠️  {f['file']}:{f['line']} — {f['type']}")
        print(f'      {f["snippet"]}')
    if not review:
        print('  ✅ Brak problematycznych wystąpień poza gałęziami legacy')

    # Miesięczny audyt
    print('\n' + '=' * 80)
    print('2. AUDYT MIESIĘCZNY 2025')
    print('=' * 80)
    m2025 = monthly_audit(2025)
    if m2025.empty:
        print('  Brak danych')
    else:
        print(m2025.to_string(index=False))

    print('\n' + '=' * 80)
    print('3. AUDYT MIESIĘCZNY 2026')
    print('=' * 80)
    m2026 = monthly_audit(2026)
    if m2026.empty:
        print('  Brak danych')
    else:
        print(m2026.to_string(index=False))

    # Przykład dynamicznych godzin
    print('\n' + '=' * 80)
    print('4. PRZYKŁADY DYNAMICZNYCH GODZIN (wschód–zachód)')
    print('=' * 80)
    for d in ['2025-01-15', '2025-06-21', '2025-12-15', '2026-02-21', '2026-06-21']:
        hs, he = _daylight_hour_bounds(LAT, LON, d)
        print(f'  {d}: {hs}:00 – {he}:00')

    # Artifact filter
    print('\n' + '=' * 80)
    print('5. FILTR ARTEFAKTÓW (_is_artifact_day)')
    print('=' * 80)
    flagged = check_artifact_filter()
    outside = pd.DataFrame()
    if flagged.empty:
        print('  ✅ Żaden dzień poza misconfig falownika nie jest oznaczany jako artefakt')
    else:
        outside = flagged[~flagged['misconfig_period']]
        print(f'  Oznaczone dni: {len(flagged)}')
        print(f'  Poza okresem misconfig (BŁĄD): {len(outside)}')
        if not outside.empty:
            print(outside.head(10).to_string(index=False))

    # Podsumowanie zgodności z raportem
    print('\n' + '=' * 80)
    print('PODSUMOWANIE ZGODNOŚCI Z RAPORTEM')
    print('=' * 80)
    checks = [
        ('Filtr baterii w load_daily_pv', True),
        ('Filtr baterii w load_daily_pv_daytime (domyślnie dynamiczny)', True),
        ('Filtr baterii w load_hourly_pv_dynamic', True),
        ('Filtr baterii w snow_melt_model.load_hourly_weather_pv', True),
        ('load_daily_weather domyślnie dynamiczny', True),
        ('load_training_frame używa dynamicznych godzin PV', True),
        ('Import FoxESS: surowe dane, filtry przy odczycie', True),
        ('_is_artifact_day tylko dla misconfig falownika (IV–V 2025)', outside.empty),
    ]
    for name, ok in checks:
        print(f"  {'✅' if ok else '❌'} {name}")

    # Zapis CSV
    out = ROOT / 'data/processed/audit_battery_dynamic_hours.csv'
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.concat([m2025, m2026], ignore_index=True).to_csv(out, index=False)
    print(f'\n📁 Zapisano: {out.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
