#!/usr/bin/env python3
"""T4.20 — generator sugestii baterii do tabeli notifications (advise-only).

Uruchamiany z daily / midday / peak po battery_advisor_report.
Upsert: cheap_window + charge_tonight_cloudy + soc_reserve dla aktywnych użytkowników.

Użycie:
    ./venv/bin/python mlops/generate_battery_suggestions.py --context morning
    ./venv/bin/python mlops/generate_battery_suggestions.py --context pre_cheap
    ./venv/bin/python mlops/generate_battery_suggestions.py --context peak
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    import argparse

    from api.db import SessionLocal, init_db
    from api.services.notifications_service import generate_suggestions_for_all_users

    parser = argparse.ArgumentParser(description='T4.20 generator sugestii baterii')
    parser.add_argument(
        '--context',
        required=True,
        choices=['morning', 'pre_cheap', 'peak'],
        help='morning=5:00, pre_cheap=12:00, peak=16:00',
    )
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        summary = generate_suggestions_for_all_users(db, args.context)
    finally:
        db.close()

    print('=' * 60)
    print(f'T4.20 SUGGESTIONS | context={summary["context"]}')
    print('=' * 60)
    print(f'users:                  {summary["users"]}')
    print(f'cheap_window:           {summary["cheap_window"]}')
    print(f'charge_tonight_cloudy:  {summary["charge_tonight_cloudy"]}')
    print(f'soc_reserve:            {summary["soc_reserve"]}')
    print('=' * 60)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
