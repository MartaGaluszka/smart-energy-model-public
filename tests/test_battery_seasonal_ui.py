"""BAT.5 rezerwa sezonowa + BAT.3 alert SoC@16 (czyste reguły, bez I/O)."""

from datetime import date, datetime
from types import SimpleNamespace

from src.optimization.battery_advisor import (
    evaluate_soc16_hold_reserve,
    seasonal_soc_reserve,
)
from api.services.battery_planner import effective_soc_min, resolve_season_name


def test_reserve_autumn_october():
    assert seasonal_soc_reserve(date(2026, 10, 15)) == 22.0


def test_reserve_autumn_mid_september():
    assert seasonal_soc_reserve(date(2026, 9, 20)) == 22.0


def test_reserve_summer_early_september():
    assert seasonal_soc_reserve(date(2026, 9, 10)) == 20.0


def test_reserve_winter_november():
    assert seasonal_soc_reserve(date(2026, 11, 5)) == 40.0


def test_reserve_summer_august():
    assert seasonal_soc_reserve(date(2026, 8, 27)) == 20.0


def test_reserve_explicit_winter_in_august():
    assert seasonal_soc_reserve(date(2026, 8, 27), season='winter') == 40.0


def test_reserve_explicit_autumn():
    assert seasonal_soc_reserve(date(2026, 8, 27), season='autumn') == 22.0


def test_auto_season_resolves_summer_in_august():
    assert resolve_season_name('auto', date(2026, 8, 27)) == 'summer'


def test_auto_season_resolves_autumn_in_october():
    assert resolve_season_name('auto', date(2026, 10, 15)) == 'autumn'


def test_auto_season_resolves_spring_in_march():
    assert resolve_season_name('auto', date(2026, 3, 15)) == 'spring'


def test_reserve_spring_march():
    assert seasonal_soc_reserve(date(2026, 3, 15)) == 20.0


def test_effective_soc_min_auto_ignores_factory_20():
    row = SimpleNamespace(season='auto', soc_min_percent=20.0)
    assert effective_soc_min(row, date(2026, 8, 27)) == 20.0
    assert effective_soc_min(row, date(2026, 10, 15)) == 22.0
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
        reserve_percent=22.0,
        min_evening=45.0,
    )
    assert rule.triggered is False


def test_soc16_triggers_afternoon_window():
    """Październik = jesień: min wieczór 45%, rezerwa 22%."""
    rule = evaluate_soc16_hold_reserve(
        soc_percent=30.0,
        as_of=datetime(2026, 10, 15, 14, 0),
        reserve_percent=22.0,
        min_evening=45.0,
    )
    assert rule.triggered is True
    assert '13' in rule.body
    assert 'rezerwy 22%' in rule.body


def test_soc16_triggers_after_16():
    rule = evaluate_soc16_hold_reserve(
        soc_percent=42.0,
        as_of=datetime(2026, 10, 15, 16, 10),
        reserve_percent=22.0,
        min_evening=45.0,
    )
    assert rule.triggered is True
    assert rule.hour_passed is True
    assert '22–6' in rule.body or '22-6' in rule.body


def test_soc16_skips_when_soc_ok():
    rule = evaluate_soc16_hold_reserve(
        soc_percent=50.0,
        as_of=datetime(2026, 10, 15, 16, 10),
        reserve_percent=22.0,
        min_evening=45.0,
    )
    assert rule.triggered is False


def test_wait_cheap_evening_peak_below_40():
    from src.optimization.battery_advisor import evaluate_below_reserve_wait_cheap

    rule = evaluate_below_reserve_wait_cheap(
        soc_percent=18.0,
        as_of=datetime(2026, 10, 15, 17, 0),  # czwartek, G12w drogo 15–22
        reserve_percent=22.0,
    )
    assert rule.triggered is True
    assert rule.next_cheap_window == '22–6'
    assert 'nie ładuj' in rule.body.lower() or 'Nie ładuj' in rule.body


def test_wait_cheap_morning_peak_points_to_afternoon():
    from src.optimization.battery_advisor import evaluate_below_reserve_wait_cheap

    rule = evaluate_below_reserve_wait_cheap(
        soc_percent=18.0,
        as_of=datetime(2026, 10, 15, 10, 0),
        reserve_percent=22.0,
    )
    assert rule.triggered is True
    assert rule.next_cheap_window == '13–15'


def test_wait_cheap_skips_in_night_window():
    from src.optimization.battery_advisor import evaluate_below_reserve_wait_cheap

    rule = evaluate_below_reserve_wait_cheap(
        soc_percent=18.0,
        as_of=datetime(2026, 10, 15, 23, 0),  # już tanio 22–6
        reserve_percent=22.0,
    )
    assert rule.triggered is False
    assert rule.in_cheap_zone is True


def test_fallback_home_suggestion_summer():
    from api.services.battery_planner import fallback_home_suggestion, get_home_suggestion

    row = SimpleNamespace(season='auto', soc_target_percent=80.0, battery_capacity_kwh=10.36)
    fb = fallback_home_suggestion(row, as_of=datetime(2026, 8, 27, 15, 0))
    assert fb['season'] == 'summer'
    assert fb['soc_reserve_percent'] == 20.0
    assert fb['automation_enabled'] is False
    assert fb['recommendation'] == 'REŻIM LATO'

    live = get_home_suggestion(row, as_of=datetime(2026, 8, 27, 15, 0))
    assert live['season'] == 'summer'
    assert live['automation_enabled'] is False


def test_fallback_home_suggestion_october_autumn():
    """Live X: auto → jesień, rezerwa 22%, FC noc gdy PV < ~8."""
    from api.services.battery_planner import fallback_home_suggestion

    row = SimpleNamespace(season='auto', soc_target_percent=80.0, battery_capacity_kwh=10.36)
    fb = fallback_home_suggestion(row, as_of=datetime(2026, 10, 15, 17, 0))
    assert fb['season'] == 'autumn'
    assert fb['soc_reserve_percent'] == 22.0
    assert fb['recommendation'] == 'REŻIM JESIEŃ'
    assert '8' in fb.get('force_charge_night_label', '') or 'PV' in fb.get('force_charge_night_label', '')


def test_wait_cheap_skips_when_above_reserve():
    from src.optimization.battery_advisor import evaluate_below_reserve_wait_cheap

    rule = evaluate_below_reserve_wait_cheap(
        soc_percent=28.0,
        as_of=datetime(2026, 10, 15, 17, 0),
        reserve_percent=22.0,
    )
    assert rule.triggered is False
