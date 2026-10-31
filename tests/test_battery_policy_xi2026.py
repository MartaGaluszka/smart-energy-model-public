"""T6.0 / porcja 1 — polityka baterii (skrócony gate XI 2026)."""

from __future__ import annotations

from api.services.battery_planner import (
    BATTERY_POLICY_BODY,
    BATTERY_POLICY_REASONS,
    BATTERY_POLICY_TITLE,
    get_battery_policy,
)


def test_get_battery_policy_advise_only_flag():
    policy = get_battery_policy()
    assert policy['automation_enabled'] is False
    assert policy['title'] == BATTERY_POLICY_TITLE
    assert policy['body'] == BATTERY_POLICY_BODY
    assert policy['reasons'] == BATTERY_POLICY_REASONS


def test_battery_policy_xi_2026_copy():
    assert 'XI 2026' in BATTERY_POLICY_TITLE
    assert '22:00' in BATTERY_POLICY_BODY
    assert 'NOTATKA_DECYZJA_AUTOMATYKA_BATERII_XI_2026' in BATTERY_POLICY_BODY
    assert any('B2' in r or 'BATTERY_CONTROL' in r for r in BATTERY_POLICY_REASONS)
