#!/usr/bin/env python
"""
Usuwa stare kopie CSV FoxESS z data/raw/ (foxess_all_*, foxess_core_*).

Domyślnie zostawia pliki z ostatnich 14 dni. Baza energy_model.db nie jest dotykana.

Użycie:
    python scripts/cleanup_foxess_raw.py              # dry-run (podgląd)
    python scripts/cleanup_foxess_raw.py --apply      # usuń
    python scripts/cleanup_foxess_raw.py --keep-days 7 --apply
    python scripts/cleanup_foxess_raw.py --keep-last 2 --apply
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / 'data' / 'raw'
PATTERN = re.compile(r'^foxess_(all_variables|core)_(\d{8})_\d{6}\.csv$')


def list_foxess_exports() -> list[tuple[Path, datetime]]:
    if not RAW_DIR.is_dir():
        return []
    out: list[tuple[Path, datetime]] = []
    for path in RAW_DIR.iterdir():
        m = PATTERN.match(path.name)
        if not m:
            continue
        stamp = datetime.strptime(m.group(2), '%Y%m%d')
        out.append((path, stamp))
    return sorted(out, key=lambda x: x[1], reverse=True)


def main() -> None:
    parser = argparse.ArgumentParser(description='Czyść stare CSV FoxESS w data/raw/')
    parser.add_argument('--apply', action='store_true', help='Faktycznie usuń pliki')
    parser.add_argument('--keep-days', type=int, default=14, help='Zachowaj pliki nowsze niż N dni (domyślnie 14)')
    parser.add_argument(
        '--keep-last',
        type=int,
        default=0,
        help='Dodatkowo zachowaj N najnowszych par plików (0 = wyłączone)',
    )
    args = parser.parse_args()

    files = list_foxess_exports()
    if not files:
        print(f'Brak plików foxess_* w {RAW_DIR}')
        return

    keep_paths: set[Path] = set()
    if args.keep_last > 0:
        unique_days = sorted({stamp.date() for _, stamp in files}, reverse=True)
        keep_day_set = set(unique_days[: args.keep_last])
        for path, stamp in files:
            if stamp.date() in keep_day_set:
                keep_paths.add(path)

    cutoff_day = (datetime.now() - timedelta(days=args.keep_days)).date()
    to_delete: list[Path] = []
    for path, stamp in files:
        if path in keep_paths:
            continue
        if stamp.date() >= cutoff_day:
            continue
        to_delete.append(path)

    total_mb = sum(p.stat().st_size for p in to_delete) / (1024 * 1024)
    print(f'Katalog: {RAW_DIR}')
    print(f'Plików FoxESS CSV: {len(files)} | do usunięcia: {len(to_delete)} (~{total_mb:.1f} MB)')
    print(f'Zachowaj: ostatnie {args.keep_days} dni', end='')
    if args.keep_last:
        print(f' + {args.keep_last} najnowsze daty eksportu', end='')
    print()

    for path in sorted(to_delete):
        prefix = 'USUŃ' if args.apply else 'DRY '
        print(f'  {prefix}: {path.name}')

    if not to_delete:
        return
    if not args.apply:
        print('\nPodgląd — uruchom z --apply aby usunąć.')
        return

    for path in to_delete:
        path.unlink()
    print(f'\n✅ Usunięto {len(to_delete)} plików.')


if __name__ == '__main__':
    main()
