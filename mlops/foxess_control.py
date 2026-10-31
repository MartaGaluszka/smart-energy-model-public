#!/usr/bin/env python3
"""
Sterowanie baterią FoxESS na podstawie battery_advisor.

Domyślnie DRY-RUN (tylko plan, bez zmian na falowniku).

Użycie:
    ./venv/bin/python mlops/foxess_control.py --context morning
    ./venv/bin/python mlops/foxess_control.py --context pre_cheap --apply
    ./venv/bin/python mlops/foxess_control.py --context evening --apply
    ./venv/bin/python mlops/foxess_control.py --stop-fc
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
        evening_stop_if_due,
        format_plan,
        plan_and_run,
        planned_stop_at,
        should_apply,
    )

    parser = argparse.ArgumentParser(description='Sterowanie baterią FoxESS (advisor → API)')
    parser.add_argument(
        '--context',
        choices=['morning', 'pre_cheap', 'peak', 'evening'],
        help='Kontekst advisora (morning / pre_cheap / peak / evening ~21:15 B2)',
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
        '--stop-fc',
        action='store_true',
        help='Timer B2: SelfUse po upływie minut FC (T6.2b; sesja z ostatniego evening --apply)',
    )
    parser.add_argument(
        '--no-read-state',
        action='store_true',
        help='Nie odczytuj falownika (oszczędza limit Fox ~1440/dobę; plan z bazy)',
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

    if args.stop_fc:
        dry_run = not should_apply(dry_run_flag=not args.apply)
        if args.apply and not control_enabled():
            print('❌ --apply wymaga BATTERY_CONTROL_ENABLED=1 w .env')
            sys.exit(1)
        status, plan, results = evening_stop_if_due(dry_run=dry_run)
        print(f'evening stop: {status}')
        if plan is not None:
            from src.optimization.battery_advisor import BatteryAdvice, BatterySnapshot, PvOutlook
            from datetime import datetime

            stub = BatteryAdvice(
                context='evening',
                as_of=datetime.now(),
                target_day=datetime.now().date().isoformat(),
                season='winter',
                tariff_zone=2,
                tariff_label='tanio',
                snapshot=BatterySnapshot(None, None, None, None, None, None),
                pv=PvOutlook(None, None, 0.0, 0.0, 0.0, 0.0),
                resilience=None,
                recommendation='STOP FC (B2 timer)',
                action='',
                details=[],
            )
            print(format_plan(stub, plan, results))
            if not args.no_log:
                append_control_log(stub, plan, results, phase='stop')
        if status == 'wait':
            sys.exit(0)
        if status.startswith('denied:'):
            print(f'⛔ {status[8:]}')
            sys.exit(2)
        return

    if not args.context:
        parser.error('Podaj --context, --stop-fc lub --status')

    dry_run = not should_apply(dry_run_flag=not args.apply)
    if args.apply and not control_enabled():
        print('❌ --apply wymaga BATTERY_CONTROL_ENABLED=1 w .env')
        print('   Bez tego używaj domyślnego dry-run.')
        sys.exit(1)

    phase = 'apply' if args.apply else 'run'
    advice, plan, results = plan_and_run(
        args.context,
        dry_run=dry_run,
        phase=phase,
        read_state=not args.no_read_state,
    )
    print(format_plan(advice, plan, results))

    if not args.no_log:
        append_control_log(
            advice,
            plan,
            results,
            phase=phase,
            planned_stop=planned_stop_at(advice) if args.context == 'evening' else None,
        )
        print(f'\n✓ log: data/processed/battery_control_log.csv')

    if dry_run:
        print('\nℹ️  Tryb DRY-RUN — falownik bez zmian.')
        print('   Aby wysłać komendy: BATTERY_CONTROL_ENABLED=1 + --apply')
    elif plan.notes and any('Apply zablokowane' in n for n in plan.notes):
        sys.exit(2)


if __name__ == '__main__':
    main()
