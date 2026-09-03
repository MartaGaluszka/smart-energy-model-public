"""T4.5 — wyłącz AC o HH:MM + zużycie nocne (bez I/O Fox)."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import create_app
from api.services.battery_planner import calculate_ac_runtime, is_ac_event_type


def _settings(**kwargs):
    defaults = dict(
        season='summer',
        soc_min_percent=20.0,
        battery_capacity_kwh=10.36,
        efficiency_pct=93.0,
        ac_power_kw=1.2,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _snap(soc: float | None):
    return SimpleNamespace(soc_percent=soc)


def test_ac_event_types():
    assert is_ac_event_type('klimatyzacja')
    assert is_ac_event_type('Upał')
    assert is_ac_event_type('upal')
    assert not is_ac_event_type('ferie')
    assert not is_ac_event_type(None)


def test_off_time_after_18_subtracts_night_house():
    row = calculate_ac_runtime(
        1.2,
        _settings(),
        as_of=datetime(2026, 9, 3, 20, 0),
        ac_day=True,
        snapshot=_snap(100.0),
        night_load_kw=0.55,
    )
    assert row['show_card'] is True
    assert row['suggested_off_at'] == '21:50'
    assert row['night_house_kwh'] == 5.5
    assert row['battery_covers_from'] == '20:00'
    assert '21:50' in row['note']


def test_before_18_battery_night_starts_at_18():
    row = calculate_ac_runtime(
        1.2,
        _settings(),
        as_of=datetime(2026, 9, 3, 16, 0),
        ac_day=False,
        snapshot=_snap(100.0),
        night_load_kw=0.55,
    )
    assert row['show_card'] is False
    assert row['battery_covers_from'] == '18:00'
    assert row['hours_until_morning'] == 12.0
    assert row['suggested_off_at'] == '18:55'


def test_low_soc_turns_off_immediately():
    row = calculate_ac_runtime(
        1.2,
        _settings(),
        as_of=datetime(2026, 9, 3, 20, 0),
        snapshot=_snap(40.0),
        night_load_kw=0.55,
    )
    assert row['hours_safe'] == 0.0
    assert row['suggested_off_at'] == '20:00'


def test_no_soc_no_off_time():
    row = calculate_ac_runtime(1.2, _settings(), snapshot=_snap(None), night_load_kw=0.55)
    assert row['suggested_off_at'] is None
    assert row['hours_safe'] == 0.0


def test_get_ac_runtime_requires_auth():
    with TestClient(create_app()) as client:
        assert client.get('/api/v1/battery/ac-runtime').status_code == 401


def test_get_ac_runtime_ok(client, auth_headers):
    snap = MagicMock(soc_percent=100.0)
    with (
        patch('src.optimization.battery_advisor.get_battery_snapshot', return_value=snap),
        patch('api.services.battery_planner.today_is_ac_day', return_value=True),
        patch('src.optimization.battery_advisor._evening_planning_load_kw', return_value=0.55),
    ):
        response = client.get('/api/v1/battery/ac-runtime', headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data['show_card'] is True
    assert data['ac_day'] is True
    assert data['suggested_off_at']
    assert data['night_load_kw'] == 0.55
    assert 'night_house_kwh' in data
    assert data['note']
