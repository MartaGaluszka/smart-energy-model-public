"""Mapowanie harmonogramu Fox ↔ schedule_windows SE."""

from __future__ import annotations

from src.data.foxess_control import ForceChargeWindow
from src.data.foxess_schedule_sync import (
    force_charge_windows_to_schedule_windows,
    fox_periods_to_schedule_windows,
    schedule_windows_to_fox_groups,
)


def test_fox_period_to_se_window():
    periods = [
        {
            'startHour': 13,
            'startMinute': 0,
            'endHour': 14,
            'endMinute': 59,
            'workMode': 'ForceCharge',
            'isRemainMode': False,
            'extraParam': {'maxSoc': 80, 'minSocOnGrid': 10},
        },
        {
            'startHour': 0,
            'startMinute': 0,
            'endHour': 23,
            'endMinute': 59,
            'workMode': 'SelfUse',
            'isRemainMode': True,
        },
    ]
    windows = fox_periods_to_schedule_windows(periods, schedule_enabled=True)
    assert len(windows) == 1
    assert windows[0]['start'] == '13:00'
    assert windows[0]['end'] == '14:59'
    assert windows[0]['mode'] == 'ForceCharge'
    assert windows[0]['enabled'] is True
    assert windows[0]['max_soc_percent'] == 80.0


def test_fox_period_enabled_even_when_master_flag_false():
    """Global enable z API bywa rozjechany z app — sloty i tak są włączone w SE."""
    periods = [
        {
            'startHour': 4,
            'startMinute': 0,
            'endHour': 5,
            'endMinute': 0,
            'workMode': 'ForceCharge',
            'isRemainMode': False,
            'extraParam': {'maxSoc': 90},
        },
    ]
    windows = fox_periods_to_schedule_windows(periods, schedule_enabled=False)
    assert len(windows) == 1
    assert windows[0]['enabled'] is True


def test_se_window_to_fox_group():
    groups = schedule_windows_to_fox_groups(
        [
            {
                'start': '22:00',
                'end': '23:00',
                'mode': 'ForceCharge',
                'enabled': True,
                'max_soc_percent': 100,
            },
            {'start': '06:00', 'end': '08:00', 'mode': 'SelfUse', 'enabled': False},
        ]
    )
    assert len(groups) == 1
    assert groups[0]['workMode'] == 'ForceCharge'
    assert groups[0]['extraParam']['maxSoc'] == 100


def test_force_charge_fallback_when_schedule_off():
    fc1 = ForceChargeWindow(enabled=True, start_hour=22.0, end_hour=6.0)
    fc2 = ForceChargeWindow(enabled=False, start_hour=4.0, end_hour=6.0)
    windows = force_charge_windows_to_schedule_windows(fc1, fc2, schedule_enabled=False)
    assert len(windows) == 1
    assert windows[0]['start'] == '22:00'
    assert windows[0]['end'] == '06:00'
