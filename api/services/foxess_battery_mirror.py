"""Odczyt/zapis harmonogramu baterii FoxESS — lustro app Fox ↔ ustawienia SE (T6.x)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from src.data.foxess_api_guard import assert_api_allowed, is_api_paused, pause_message
from src.data.foxess_schedule_sync import (
    force_charge_windows_to_schedule_windows,
    fox_periods_to_schedule_windows,
    schedule_windows_to_fox_groups,
)
from src.data.foxess_control import FoxEssControl, _fmt_hour


def _ctrl() -> FoxEssControl:
    assert_api_allowed()
    return FoxEssControl()


def read_fox_battery_mirror() -> dict[str, Any]:
    """Live stan falownika + bloki harmonogramu w formacie SE."""
    if is_api_paused():
        return {
            'ok': False,
            'error': pause_message(),
            'schedule_windows': [],
            'schedule_source': 'unavailable',
        }

    try:
        ctrl = _ctrl()
        state = ctrl.read_state()
        sched = ctrl.read_schedule()
        enabled = bool(sched.get('enabled'))
        periods = sched.get('periods') or []
        windows = fox_periods_to_schedule_windows(periods, schedule_enabled=enabled)
        if not windows and not enabled:
            windows = force_charge_windows_to_schedule_windows(
                state.force_charge_1,
                state.force_charge_2,
                schedule_enabled=False,
            )
        source = 'fox_schedule' if enabled else ('fox_force_charge' if windows else 'fox_empty')
        return {
            'ok': True,
            'as_of': datetime.now().isoformat(timespec='seconds'),
            'schedule_source': source,
            'fox_schedule_enabled': enabled,
            'work_mode': state.work_mode,
            'min_soc_percent': state.min_soc,
            'min_soc_on_grid_percent': state.min_soc_on_grid,
            'force_charge_1': {
                'enabled': state.force_charge_1.enabled,
                'start': _fmt_hour(state.force_charge_1.start_hour) if state.force_charge_1.enabled else None,
                'end': _fmt_hour(state.force_charge_1.end_hour) if state.force_charge_1.enabled else None,
            },
            'force_charge_2': {
                'enabled': state.force_charge_2.enabled,
                'start': _fmt_hour(state.force_charge_2.start_hour) if state.force_charge_2.enabled else None,
                'end': _fmt_hour(state.force_charge_2.end_hour) if state.force_charge_2.enabled else None,
            },
            'schedule_windows': windows,
            'period_count': len(periods),
        }
    except Exception as exc:
        return {
            'ok': False,
            'error': str(exc),
            'schedule_windows': [],
            'schedule_source': 'error',
        }


def merge_fox_into_settings_payload(base: dict[str, Any], *, persist_row=None) -> dict[str, Any]:
    """Nadpisuje ``schedule_windows`` danymi z Fox gdy odczyt się uda."""
    fox = read_fox_battery_mirror()
    out = dict(base)
    out['fox_mirror'] = {k: v for k, v in fox.items() if k != 'schedule_windows'}
    if not fox.get('ok'):
        out['schedule_source'] = 'database'
        return out

    fox_windows = fox.get('schedule_windows') or []
    if fox_windows:
        out['schedule_windows'] = fox_windows
        out['schedule_source'] = fox.get('schedule_source') or 'fox'
        out['fox_schedule_enabled'] = fox.get('fox_schedule_enabled')
        if persist_row is not None:
            persist_row.schedule_windows_json = json.dumps(fox_windows, ensure_ascii=False)
            if hasattr(persist_row, 'schedule_preset'):
                persist_row.schedule_preset = 'custom'
    else:
        out['schedule_source'] = 'database'
    return out


def push_schedule_windows_to_fox(windows: list[dict], *, dry_run: bool = False) -> dict[str, Any]:
    """Zapis włączonych bloków SE → harmonogram Fox (app widzi te same sloty)."""
    assert_api_allowed()
    groups = schedule_windows_to_fox_groups(windows)
    if not groups:
        return {'ok': False, 'error': 'Brak włączonych bloków harmonogramu do wysłania.'}
    ctrl = _ctrl()
    result = ctrl.set_work_schedule(groups, enable=True, dry_run=dry_run)
    return {'ok': True, 'groups_sent': len(groups), 'result': result}
