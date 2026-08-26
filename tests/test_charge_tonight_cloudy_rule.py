"""Reguła: niski SoC + jutro słabe PV → ładuj od 22:00."""

from datetime import datetime

from src.optimization.battery_advisor import evaluate_charge_tonight_cloudy


def test_triggers_on_low_soc_and_weak_tomorrow():
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=43.0,
        tomorrow_pv_kwh=11.6,
        as_of=datetime(2026, 8, 25, 17, 0),
    )
    assert rule.triggered is True
    assert '22:00' in rule.body
    assert rule.recommendation.startswith('ŁADUJ OD 22:00')


def test_skips_when_soc_ok():
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=80.0,
        tomorrow_pv_kwh=11.6,
        as_of=datetime(2026, 8, 25, 17, 0),
    )
    assert rule.triggered is False


def test_skips_when_tomorrow_sunny():
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=43.0,
        tomorrow_pv_kwh=32.0,
        as_of=datetime(2026, 8, 25, 17, 0),
    )
    assert rule.triggered is False


def test_skips_weekend():
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=43.0,
        tomorrow_pv_kwh=11.6,
        as_of=datetime(2026, 8, 22, 17, 0),  # sobota
    )
    assert rule.triggered is False


def test_skips_after_22():
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=43.0,
        tomorrow_pv_kwh=11.6,
        as_of=datetime(2026, 8, 25, 22, 15),
    )
    assert rule.triggered is False
