"""
Mapowanie rekomendacji battery_advisor → plan sterowania FoxESS.

Domyślnie tylko plan (dry-run). Realne API wymaga BATTERY_CONTROL_ENABLED=1 + --apply.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

import pandas as pd

from src.data.foxess_control import BatteryControlState, ForceChargeWindow, FoxEssControl
from src.optimization.battery_advisor import BatteryAdvice, Context, advise
from src.optimization.g12w_tariff import is_weekend, weekday_force_charge_windows

ActionKind = Literal[
    'set_force_charge_windows',
    'set_work_mode',
    'set_min_soc',
    'noop',
]

LOG_FILE = 'data/processed/battery_control_log.csv'


@dataclass
class ControlAction:
    kind: ActionKind
    description: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ControlPlan:
    context: Context
    as_of: datetime
    recommendation: str
    dry_run: bool
    actions: list[ControlAction]
    notes: list[str] = field(default_factory=list)

    def has_changes(self) -> bool:
        return any(a.kind != 'noop' for a in self.actions)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, '').strip()
    return float(raw) if raw else default


def _night_window() -> ForceChargeWindow:
    start, end = weekday_force_charge_windows()[0]
    return ForceChargeWindow(
        enabled=True,
        start_hour=start.hour + start.minute / 60.0,
        end_hour=end.hour + end.minute / 60.0,
    )


def _midday_window() -> ForceChargeWindow:
    start, end = weekday_force_charge_windows()[1]
    return ForceChargeWindow(
        enabled=True,
        start_hour=start.hour + start.minute / 60.0,
        end_hour=end.hour + end.minute / 60.0,
    )


def _disabled_window() -> ForceChargeWindow:
    return ForceChargeWindow(enabled=False, start_hour=0.0, end_hour=0.0)


def control_enabled() -> bool:
    return os.getenv('BATTERY_CONTROL_ENABLED', '0').strip().lower() in ('1', 'true', 'yes')


def should_apply(dry_run_flag: bool | None = None) -> bool:
    """True tylko gdy master switch ON i jawne apply (flaga lub env)."""
    if not control_enabled():
        return False
    if dry_run_flag is not None:
        return not dry_run_flag
    return os.getenv('BATTERY_CONTROL_APPLY', '0').strip().lower() in ('1', 'true', 'yes')


def build_plan(advice: BatteryAdvice, *, state: BatteryControlState | None = None) -> ControlPlan:
    """Z rekomendacji advisora zbuduj listę akcji na falownik."""
    rec = advice.recommendation
    actions: list[ControlAction] = []
    notes: list[str] = []
    winter = advice.season == 'winter'
    weekend = is_weekend(advice.as_of.date())
    soc = advice.snapshot.soc_percent
    target = _env_float('BATTERY_SOC_TARGET', 80.0)
    reserve = _env_float('BATTERY_SOC_RESERVE_WINTER', 40.0)

    night = _night_window()
    midday = _midday_window()
    midday_off = _disabled_window()

    if advice.context == 'morning':
        if not winter:
            actions.append(ControlAction('noop', 'Tryb letni — bez automatycznego ForceCharge.'))
        elif rec == 'ŁADUJ Z SIECI (TANIO)':
            actions.append(ControlAction(
                'set_force_charge_windows',
                'Włącz okno nocne 22:00–6:00 (G12w tanio).',
                {'period1': night, 'period2': midday_off},
            ))
            if advice.as_of.hour < 6:
                actions.append(ControlAction(
                    'set_work_mode',
                    'Natychmiastowe ładowanie z sieci do 6:00 (ForceCharge).',
                    {'mode': 'ForceCharge'},
                ))
        elif rec in ('SOC OK', 'POCZEKAJ NA PV'):
            actions.append(ControlAction(
                'set_work_mode',
                'Autokonsumpcja — bez wymuszonego ładowania z sieci.',
                {'mode': 'SelfUse'},
            ))
            if rec == 'POCZEKAJ NA PV':
                notes.append('Okno 22–6 pozostaje skonfigurowane na zimę, ale tryb SelfUse teraz.')
        elif rec.startswith('ZIMNO') or rec.startswith('AWARIA'):
            actions.append(ControlAction(
                'set_force_charge_windows',
                'Pełne okna tanich stref — maks. rezerwa na przerwy.',
                {'period1': night, 'period2': midday},
            ))
            actions.append(ControlAction(
                'set_min_soc',
                f'Podnieś rezerwę min. SoC do {reserve:.0f}%.',
                {'min_soc': reserve},
            ))
        else:
            actions.append(ControlAction('noop', f'Brak reguły sterowania dla: {rec}'))

    elif advice.context == 'pre_cheap':
        if not winter or weekend:
            actions.append(ControlAction('noop', 'Weekend / lato — okno 13–15 nie jest krytyczne.'))
        elif rec == 'ŁADUJ 13:00–15:00 (G12w TANIO)':
            actions.append(ControlAction(
                'set_force_charge_windows',
                'Włącz okno południowe 13:00–15:00 + nocne 22:00–6:00.',
                {'period1': night, 'period2': midday},
            ))
        elif rec == 'SOC OK — POMIŃ FORCE CHARGE':
            actions.append(ControlAction(
                'set_force_charge_windows',
                f'SoC ≥ cel ({target:.0f}%) — wyłącz okno 13–15, zostaw noc 22–6.',
                {'period1': night, 'period2': midday_off},
            ))
        elif rec.startswith('ZIMNO') or rec.startswith('AWARIA'):
            actions.append(ControlAction(
                'set_force_charge_windows',
                'Po awarii / wysokim load — włącz oba okna tanio.',
                {'period1': night, 'period2': midday},
            ))
        else:
            actions.append(ControlAction('noop', f'Brak reguły sterowania dla: {rec}'))

    else:  # peak
        actions.append(ControlAction(
            'set_work_mode',
            'Szczyt G12w — autokonsumpcja, rozładowuj baterię zamiast importu.',
            {'mode': 'SelfUse'},
        ))
        if winter and soc is not None and soc < _env_float('BATTERY_SOC_MIN_EVENING', 50.0):
            notes.append('Niski SoC — jutro priorytet ładowania w 22–6 / 13–15.')
        if winter and (rec.startswith('ZIMNO') or rec.startswith('AWARIA')):
            actions.append(ControlAction(
                'set_min_soc',
                f'Zimowa rezerwa min. SoC {reserve:.0f}%.',
                {'min_soc': reserve},
            ))

    if state is not None:
        notes.extend(_diff_notes(actions, state))

    return ControlPlan(
        context=advice.context,
        as_of=advice.as_of,
        recommendation=rec,
        dry_run=True,
        actions=actions,
        notes=notes,
    )


def _diff_notes(actions: list[ControlAction], state: BatteryControlState) -> list[str]:
    """Porównaj plan z aktualnym stanem falownika."""
    diffs: list[str] = []
    for action in actions:
        if action.kind == 'set_work_mode':
            mode = action.params.get('mode')
            if mode and state.work_mode and mode != state.work_mode:
                diffs.append(f'Tryb: {state.work_mode} → {mode}')
        elif action.kind == 'set_force_charge_windows':
            p1 = action.params.get('period1')
            p2 = action.params.get('period2')
            if p1 and (p1.enabled != state.force_charge_1.enabled
                       or abs(p1.start_hour - state.force_charge_1.start_hour) > 0.01
                       or abs(p1.end_hour - state.force_charge_1.end_hour) > 0.01):
                diffs.append(f'Okno 1: {state.force_charge_1.label()} → {p1.label()}')
            if p2 and (p2.enabled != state.force_charge_2.enabled
                       or abs(p2.start_hour - state.force_charge_2.start_hour) > 0.01
                       or abs(p2.end_hour - state.force_charge_2.end_hour) > 0.01):
                diffs.append(f'Okno 2: {state.force_charge_2.label()} → {p2.label()}')
        elif action.kind == 'set_min_soc':
            target = action.params.get('min_soc')
            if target is not None and state.min_soc is not None and abs(target - state.min_soc) >= 1:
                diffs.append(f'Min SoC: {state.min_soc:.0f}% → {target:.0f}%')
    if not diffs:
        diffs.append('Stan falownika zgodny z planem (brak zmian).')
    return diffs


def execute_plan(
    plan: ControlPlan,
    controller: FoxEssControl | None = None,
    *,
    dry_run: bool = True,
) -> list[dict[str, Any]]:
    controller = controller or FoxEssControl()
    results: list[dict[str, Any]] = []
    plan.dry_run = dry_run

    for action in plan.actions:
        if action.kind == 'noop':
            results.append({'dry_run': dry_run, 'action': 'noop', 'description': action.description})
            continue
        if action.kind == 'set_force_charge_windows':
            results.append(controller.set_force_charge_windows(
                period1=action.params.get('period1'),
                period2=action.params.get('period2'),
                dry_run=dry_run,
            ))
        elif action.kind == 'set_work_mode':
            results.append(controller.set_work_mode(
                action.params['mode'],
                dry_run=dry_run,
            ))
        elif action.kind == 'set_min_soc':
            results.append(controller.set_min_soc(
                min_soc=action.params.get('min_soc'),
                min_soc_on_grid=action.params.get('min_soc_on_grid'),
                dry_run=dry_run,
            ))
    return results


def plan_and_run(
    context: Context,
    *,
    as_of: datetime | None = None,
    dry_run: bool = True,
    read_state: bool = True,
) -> tuple[BatteryAdvice, ControlPlan, list[dict[str, Any]]]:
    advice = advise(context, as_of=as_of)
    state = None
    controller = None
    if read_state:
        try:
            controller = FoxEssControl()
            state = controller.read_state()
        except (ValueError, RuntimeError) as exc:
            plan = build_plan(advice)
            plan.notes.append(f'⚠️ Brak odczytu stanu FoxESS: {exc}')
            return advice, plan, []

    plan = build_plan(advice, state=state)
    results = execute_plan(plan, controller, dry_run=dry_run)
    return advice, plan, results


def format_plan(advice: BatteryAdvice, plan: ControlPlan, results: list[dict[str, Any]]) -> str:
    mode = 'DRY-RUN' if plan.dry_run else 'APPLY'
    ctx_labels = {
        'morning': 'PORANEK — sterowanie baterią',
        'pre_cheap': 'PRZED 13:00 — ForceCharge',
        'peak': 'SZCZYT — tryb SelfUse',
    }
    lines = [
        '=' * 60,
        f'FOXESS CONTROL [{mode}] — {ctx_labels[plan.context]}',
        f'{advice.as_of.strftime("%Y-%m-%d %H:%M")}  |  rekomendacja: {plan.recommendation}',
        '=' * 60,
    ]
    if not plan.has_changes():
        lines.append('→ Brak akcji sterujących (noop).')
    for i, action in enumerate(plan.actions, 1):
        prefix = '○' if action.kind == 'noop' else '→'
        lines.append(f'{prefix} [{i}] {action.description}')
    if plan.notes:
        lines.append('')
        lines.append('  --- Stan / uwagi ---')
        for note in plan.notes:
            lines.append(f'  • {note}')
    if results:
        applied = sum(1 for r in results if r.get('action') != 'noop' and not r.get('dry_run'))
        lines.append('')
        lines.append(f'  Wykonano API: {applied} akcji')
    lines.append('=' * 60)
    return '\n'.join(lines)


def append_control_log(
    advice: BatteryAdvice,
    plan: ControlPlan,
    results: list[dict[str, Any]],
    path: str | None = None,
) -> None:
    path = path or LOG_FILE
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    row = {
        'logged_at': advice.as_of.isoformat(timespec='seconds'),
        'context': plan.context,
        'dry_run': plan.dry_run,
        'recommendation': plan.recommendation,
        'soc_percent': advice.snapshot.soc_percent,
        'actions': '; '.join(a.description for a in plan.actions if a.kind != 'noop'),
        'applied_count': sum(
            1 for r in results if r.get('action') != 'noop' and not r.get('dry_run')
        ),
    }
    df = pd.DataFrame([row])
    header = not os.path.exists(path)
    df.to_csv(path, mode='a', header=header, index=False)
