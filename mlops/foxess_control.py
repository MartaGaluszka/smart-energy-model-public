#!/usr/bin/env python3
"""
Sterowanie baterią FoxESS na podstawie battery_advisor.

Domyślnie DRY-RUN (tylko plan, bez zmian na falowniku).

Użycie:
    ./venv/bin/python mlops/foxess_control.py --context morning
    ./venv/bin/python mlops/foxess_control.py --context pre_cheap --apply
    ./venv/bin/python mlops/foxess_control.py --status
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    import argparse

    from src.data.foxess_control import FoxEssControl
    from src.optimization.battery_control import (
        append_control_log,
        control_enabled,
        format_plan,
        plan_and_run,
        should_apply,
    )

    parser = argparse.ArgumentParser(description='Sterowanie baterią FoxESS (advisor → API)')
    parser.add_argument(
        '--context',
        choices=['morning', 'pre_cheap', 'peak'],
        help='Kontekst advisora (morning / pre_cheap / peak)',
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Pokaż aktualny stan falownika (tryb, okna ForceCharge, min SoC)',
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Wyślij komendy do API (wymaga BATTERY_CONTROL_ENABLED=1 w .env)',
    )
    parser.add_argument(
        '--no-log',
        action='store_true',
        help='Nie dopisuj do battery_control_log.csv',
    )
    args = parser.parse_args()

    if args.status:
        ctrl = FoxEssControl()
        state = ctrl.read_state()
        print('=' * 60)
        print('FOXESS — stan baterii / falownika')
        print('=' * 60)
        for line in state.summary_lines():
            print(f'  {line}')
        print('=' * 60)
        return

    if not args.context:
        parser.error('Podaj --context lub --status')

    dry_run = not should_apply(dry_run_flag=not args.apply)
    if args.apply and not control_enabled():
        print('❌ --apply wymaga BATTERY_CONTROL_ENABLED=1 w .env')
        print('   Bez tego używaj domyślnego dry-run.')
        sys.exit(1)

    advice, plan, results = plan_and_run(args.context, dry_run=dry_run)
    print(format_plan(advice, plan, results))

    if not args.no_log:
        append_control_log(advice, plan, results)
        print(f'\n✓ log: data/processed/battery_control_log.csv')

    if dry_run:
        print('\nℹ️  Tryb DRY-RUN — falownik bez zmian.')
        print('   Aby wysłać komendy: BATTERY_CONTROL_ENABLED=1 + --apply')


if __name__ == '__main__':
    main()
