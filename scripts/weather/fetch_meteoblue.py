#!/usr/bin/env python
"""
Pobierz Meteoblue Free API → JSON + weather_notes + stub markdown.

Użycie:
  PYTHONPATH=$PWD ./venv/bin/python scripts/weather/fetch_meteoblue.py
  PYTHONPATH=$PWD ./venv/bin/python scripts/weather/fetch_meteoblue.py --days 3 --dry-run
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')

from src.data.meteoblue_client import (  # noqa: E402
    aggregate_daily,
    fetch_forecast,
    save_raw_json,
    write_stub_markdown,
)
from src.data.weather_notes import insert_note  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description='Fetch Meteoblue Free API → weather_notes')
    p.add_argument('--days', type=int, default=3, help='ile dni od dziś zapisać do DB (domyślnie 3)')
    p.add_argument('--dry-run', action='store_true', help='nie zapisuj do DB / plików')
    p.add_argument('--no-db', action='store_true', help='pomiń weather_notes')
    p.add_argument('--no-stub', action='store_true', help='pomiń stub markdown')
    args = p.parse_args()

    payload = fetch_forecast()
    days = aggregate_daily(payload)
    if not days:
        print('❌ Brak zagregowanych dni z odpowiedzi MB')
        return 1

    today = date.today().isoformat()
    keep = []
    for d in days:
        if d['note_day'] < today:
            continue
        keep.append(d)
        if len(keep) >= args.days:
            break
    if not keep:
        keep = days[: args.days]

    print(f'MB: {len(keep)} dni (z {len(days)} w odpowiedzi)')
    for d in keep:
        print(
            f"  {d['note_day']}: cloud={d.get('cloud_cover_pct')}% "
            f"precip={d.get('precip_mm')} mm Pmax={d.get('precip_prob_pct')}% "
            f"Tmax={d.get('temperature_max_c')}"
        )

    if args.dry_run:
        print('(dry-run — bez zapisu)')
        return 0

    raw_path = save_raw_json(payload)
    print(f'JSON: {raw_path}')

    if not args.no_stub:
        stub = write_stub_markdown(keep, raw_path=raw_path)
        print(f'Stub: {stub}')

    if not args.no_db:
        recorded_at = datetime.now().replace(microsecond=0).isoformat()
        for d in keep:
            row_id = insert_note(
                note_day=d['note_day'],
                source='Meteoblue',
                note_kind='daily_summary',
                recorded_at=recorded_at,
                cloud_cover_pct=d.get('cloud_cover_pct'),
                uv_index=d.get('uv_index'),
                precip_mm=d.get('precip_mm'),
                rain_mm=d.get('precip_mm'),
                precip_prob_pct=d.get('precip_prob_pct'),
                wind_kmh=d.get('wind_kmh'),
                note_text=d.get('note_text'),
            )
            print(f'  weather_notes id={row_id} day={d["note_day"]}')

    print('✓ Meteoblue fetch OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
