#!/usr/bin/env python
"""Ustaw / sprawdź / usuń 24h (lub N h) pauzę FoxESS Cloud API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.foxess_api_guard import (  # noqa: E402
    clear_pause,
    is_api_paused,
    pause_message,
    paused_until,
    set_pause_hours,
)


def main() -> int:
    p = argparse.ArgumentParser(description='Pauza FoxESS API (limit 40402)')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument(
        '--enable',
        nargs='?',
        const=24.0,
        type=float,
        metavar='HOURS',
        help='włącz pauzę (domyślnie 24 h; opcjonalnie --enable 12)',
    )
    g.add_argument('--status', action='store_true', help='pokaż stan pauzy')
    g.add_argument('--clear', action='store_true', help='usuń pauzę (plik + można FOXESS_SYNC_DISABLED=0)')
    args = p.parse_args()

    if args.status:
        print(pause_message())
        u = paused_until()
        print(f'paused={is_api_paused()} until={u.isoformat() if u else "—"}')
        return 0
    if args.clear:
        clear_pause()
        print('✓ Usunięto plik pauzy. Ustaw FOXESS_SYNC_DISABLED=0 w .env gdy quota wróci.')
        return 0
    hours = float(args.enable)
    until = set_pause_hours(hours)
    print(f'✓ Pauza FoxESS API do {until.strftime("%Y-%m-%d %H:%M:%S")} ({hours:g} h)')
    print(f'  Plik: {ROOT / "data" / ".foxess_api_pause_until"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
