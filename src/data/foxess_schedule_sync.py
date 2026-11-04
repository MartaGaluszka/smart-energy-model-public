"""Mapowanie harmonogramu FoxESS (app / scheduler API) ↔ bloki SE (schedule_windows)."""

from __future__ import annotations

from typing import Any


def _hhmm(hour: int, minute: int) -> str:
    return f'{int(hour) % 24:02d}:{int(minute) % 60:02d}'


def _parse_hhmm(value: str) -> tuple[int, int] | None:
    try:
        parts = str(value).strip().split(':')
        h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
    except (TypeError, ValueError, IndexError):
        return None
    return None


def fox_period_to_window(period: dict[str, Any], *, schedule_enabled: bool) -> dict[str, Any] | None:
    """Jeden segment z ``get_schedule()['periods']`` → blok SE."""
    if not period or period.get('isRemainMode'):
        return None
    mode = str(period.get('workMode') or 'SelfUse')
    if mode not in ('ForceCharge', 'SelfUse', 'ForceDischarge'):
        mode = 'SelfUse'
    extra = period.get('extraParam') or {}
    # Slot w ``groups`` Fox = skonfigurowany okres (jak aktywny w app), niezależnie od
    # globalnego ``enable`` w API (często False mimo włączonego harmonogramu w UI).
    window: dict[str, Any] = {
        'start': _hhmm(int(period.get('startHour', 0)), int(period.get('startMinute', 0))),
        'end': _hhmm(int(period.get('endHour', 0)), int(period.get('endMinute', 0))),
        'mode': mode,
        'enabled': True,
    }
    max_soc = extra.get('maxSoc')
    if max_soc is not None:
        try:
            window['max_soc_percent'] = float(max_soc)
        except (TypeError, ValueError):
            pass
    min_grid = extra.get('minSocOnGrid')
    if min_grid is not None:
        try:
            window['min_soc_on_grid_percent'] = float(min_grid)
        except (TypeError, ValueError):
            pass
    return window


def fox_periods_to_schedule_windows(
    periods: list[dict[str, Any]] | None,
    *,
    schedule_enabled: bool,
) -> list[dict]:
    out: list[dict] = []
    for p in periods or []:
        w = fox_period_to_window(p, schedule_enabled=schedule_enabled)
        if w is not None:
            out.append(w)
    return out


def schedule_window_to_fox_group(window: dict[str, Any]) -> dict[str, Any] | None:
    """Blok SE (włączony) → struktura ``groups`` dla ``set_schedule``."""
    if not window.get('enabled', False):
        return None
    start = _parse_hhmm(str(window.get('start') or ''))
    end = _parse_hhmm(str(window.get('end') or ''))
    if start is None or end is None:
        return None
    sh, sm = start
    eh, em = end
    mode = str(window.get('mode') or 'SelfUse')
    if mode not in ('ForceCharge', 'SelfUse', 'ForceDischarge'):
        mode = 'SelfUse'
    extra: dict[str, Any] = {}
    if window.get('min_soc_on_grid_percent') is not None:
        extra['minSocOnGrid'] = int(round(float(window['min_soc_on_grid_percent'])))
    elif window.get('max_soc_percent') is not None:
        extra['minSocOnGrid'] = 10
    if window.get('max_soc_percent') is not None and 'ForceCharge' in mode:
        extra['maxSoc'] = int(round(float(window['max_soc_percent'])))
    if 'ForceCharge' in mode and extra.get('maxSoc') is not None:
        extra['fdSoc'] = extra['maxSoc']
    group: dict[str, Any] = {
        'startHour': sh,
        'startMinute': sm,
        'endHour': eh,
        'endMinute': em,
        'workMode': mode,
        'isRemainMode': False,
    }
    if extra:
        group['extraParam'] = extra
    return group


def schedule_windows_to_fox_groups(windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for w in windows:
        g = schedule_window_to_fox_group(w)
        if g is not None:
            groups.append(g)
    return groups


def force_charge_windows_to_schedule_windows(
    fc1: Any,
    fc2: Any,
    *,
    schedule_enabled: bool,
) -> list[dict]:
    """Gdy harmonogram wyłączony — pokaż okna ForceCharge z ``get_charge``."""
    if schedule_enabled:
        return []

    from src.data.foxess_control import _fmt_hour

    out: list[dict] = []
    for idx, raw in enumerate((fc1, fc2), start=1):
        if raw is None or not getattr(raw, 'enabled', False):
            continue
        out.append(
            {
                'start': _fmt_hour(float(getattr(raw, 'start_hour', 0))),
                'end': _fmt_hour(float(getattr(raw, 'end_hour', 0))),
                'mode': 'ForceCharge',
                'enabled': True,
                'source': f'force_charge_{idx}',
            }
        )
    return out
