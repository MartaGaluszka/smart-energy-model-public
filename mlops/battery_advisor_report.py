#!/usr/bin/env python3
"""
Raport stanu baterii + rekomendacja G12w / PV.

Użycie:
    ./venv/bin/python mlops/battery_advisor_report.py --context morning
    ./venv/bin/python mlops/battery_advisor_report.py --context pre_cheap
    ./venv/bin/python mlops/battery_advisor_report.py --context peak
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    import argparse

    from src.optimization.battery_advisor import advise, append_advice_log, format_advice

    parser = argparse.ArgumentParser(description='Rekomendacja baterii (G12w + PV)')
    parser.add_argument(
        '--context',
        required=True,
        choices=['morning', 'pre_cheap', 'peak'],
        help='morning=5:00, pre_cheap=12:00, peak=16:00',
    )
    parser.add_argument('--no-log', action='store_true', help='Nie dopisuj do battery_advisor_log.csv')
    args = parser.parse_args()

    advice = advise(args.context)
    print(format_advice(advice))
    if not args.no_log:
        append_advice_log(advice)
        print(f'\n✓ log: data/processed/battery_advisor_log.csv')


if __name__ == '__main__':
    main()
