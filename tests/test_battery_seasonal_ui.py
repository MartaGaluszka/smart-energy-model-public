"""BAT.5 rezerwa sezonowa + BAT.3 alert SoC@16 (czyste reguły, bez I/O)."""

from datetime import date, datetime
from types import SimpleNamespace

from src.optimization.battery_advisor import (
    evaluate_soc16_hold_reserve,
    seasonal_soc_reserve,
)
from api.services.battery_planner import effective_soc_min, resolve_season_name


def test_reserve_winter_october():
    assert seasonal_soc_reserve(date(2026, 10, 15)) == 40.0


def test_reserve_summer_august():
    assert seasonal_soc_reserve(date(2026, 8, 27)) == 15.0


def test_reserve_explicit_winter_in_august():
    assert seasonal_soc_reserve(date(2026, 8, 27), season='winter') == 40.0


def test_auto_season_resolves_summer_in_august():
    assert resolve_season_name('auto', date(2026, 8, 27)) == 'summer'


def test_auto_season_resolves_winter_in_january():
    assert resolve_season_name('auto', date(2026, 1, 15)) == 'winter'


def test_effective_soc_min_auto_ignores_factory_20():
    row = SimpleNamespace(season='auto', soc_min_percent=20.0)
    assert effective_soc_min(row, date(2026, 8, 27)) == 15.0
    assert effective_soc_min(row, date(2026, 1, 15)) == 40.0


def test_effective_soc_min_explicit_winter_keeps_custom():
    row = SimpleNamespace(season='winter', soc_min_percent=35.0)
    assert effective_soc_min(row, date(2026, 8, 27)) == 35.0


def test_effective_soc_min_explicit_winter_syncs_factory_20():
    row = SimpleNamespace(season='winter', soc_min_percent=20.0)
    assert effective_soc_min(row, date(2026, 8, 27)) == 40.0


def test_soc16_skips_before_13():
    rule = evaluate_soc16_hold_reserve(
        soc_percent=30.0,
        as_of=datetime(2026, 10, 15, 12, 0),
        reserve_percent=40.0,
        min_evening=50.0,
    )
    assert rule.triggered is False


def test_soc16_triggers_afternoon_window():
    rule = evaluate_soc16_hold_reserve(
        soc_percent=30.0,
        as_of=datetime(2026, 10, 15, 14, 0),
        reserve_percent=40.0,
        min_evening=50.0,
    )
    assert rule.triggered is True
    assert '13' in rule.body
    assert 'rezerwy 40%' in rule.body


def test_soc16_triggers_after_16():
    rule = evaluate_soc16_hold_reserve(
        soc_percent=42.0,
        as_of=datetime(2026, 10, 15, 16, 10),
        reserve_percent=40.0,
        min_evening=50.0,
    )
    assert rule.triggered is True
    assert rule.hour_passed is True
    assert '22–6' in rule.body or '22-6' in rule.body


def test_soc16_skips_when_soc_ok():
    rule = evaluate_soc16_hold_reserve(
        soc_percent=62.0,
        as_of=datetime(2026, 10, 15, 16, 10),
        reserve_percent=40.0,
        min_evening=50.0,
    )
    assert rule.triggered is False
