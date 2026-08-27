"""Reguła: niski SoC + jutro słabe PV → ładuj od 22:00."""

from datetime import datetime

from src.optimization.battery_advisor import (
    evaluate_charge_tonight_cloudy,
    fc_minutes_for_delta_soc,
    winter_night_target_soc,
)


def test_thirty_min_is_fifty_percent():
    from src.optimization.battery_advisor import NOMINAL_CAPACITY_KWH

    assert NOMINAL_CAPACITY_KWH == 10.36
    assert round(NOMINAL_CAPACITY_KWH * 0.50, 2) == 5.18  # 30 min ≈ +50 pp
    assert fc_minutes_for_delta_soc(50) == 30
    assert fc_minutes_for_delta_soc(25) == 15
    assert fc_minutes_for_delta_soc(0) == 0


def test_winter_target_table():
    assert winter_night_target_soc(-4.0, 20.0) == 95.0
    assert winter_night_target_soc(2.0, 11.0) == 95.0
    assert winter_night_target_soc(2.0, 14.0) is None
    assert winter_night_target_soc(8.0, 6.0) == 80.0
    assert winter_night_target_soc(8.0, 15.0) is None
    assert winter_night_target_soc(None, 11.0) == 90.0
    assert winter_night_target_soc(None, 14.0) is None


def test_triggers_on_low_soc_and_weak_tomorrow():
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=43.0,
        tomorrow_pv_kwh=11.6,
        as_of=datetime(2026, 10, 15, 17, 0),  # zima: T nieznana, PV < 12 → do 90%
    )
    assert rule.triggered is True
    assert '22:00' in rule.body
    assert rule.recommendation.startswith('ŁADUJ OD 22:00')
    assert rule.fc_minutes == fc_minutes_for_delta_soc(90.0 - 43.0)
    assert '30 min' in rule.body


def test_frost_charges_even_if_tomorrow_sunny():
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=55.0,
        tomorrow_pv_kwh=20.0,
        tomorrow_temp_c=-6.0,
        as_of=datetime(2026, 1, 14, 17, 0),  # środa
    )
    assert rule.triggered is True
    assert rule.target_soc_percent == 95.0
    assert rule.fc_minutes == fc_minutes_for_delta_soc(40.0)


def test_mild_sunny_skips_fill():
    """T ≥ 5°C i PV ≥ 12 kWh — dach pokrywa szczyt, nie pełnić."""
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=43.0,
        tomorrow_pv_kwh=15.0,
        tomorrow_temp_c=8.0,
        as_of=datetime(2026, 10, 15, 17, 0),
    )
    assert rule.triggered is False
    assert rule.skip_reason == 'covered'


def test_wear_skip_when_little_missing():
    """SoC 72% → 80% = +8 pp ≈ 5 min — za mało vs cykl LFP."""
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=72.0,
        tomorrow_pv_kwh=6.0,
        tomorrow_temp_c=8.0,
        as_of=datetime(2026, 10, 15, 17, 0),
    )
    assert rule.triggered is False
    assert rule.skip_reason == 'wear'


def test_autumn_mid_september_uses_b2():
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=43.0,
        tomorrow_pv_kwh=14.0,
        tomorrow_temp_c=12.0,
        as_of=datetime(2026, 9, 16, 17, 0),  # środa, od 15.09 B2
    )
    assert rule.triggered is False
    assert rule.skip_reason == 'covered'


def test_summer_skips_at_24_percent_even_if_tomorrow_weak():
    """Lekcja 25–26.08: 24% na noc wystarcza; nie pełnić do 75% pod deszcz jutro."""
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=24.0,
        tomorrow_pv_kwh=11.6,
        as_of=datetime(2026, 8, 25, 17, 0),
    )
    assert rule.triggered is False


def test_summer_short_fc_when_below_20_and_tomorrow_upto_10():
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=18.0,
        tomorrow_pv_kwh=9.0,  # jutro do 10 kWh — nadal cap 15 min, nie 75%
        as_of=datetime(2026, 8, 25, 17, 0),
    )
    assert rule.triggered is True
    assert '15 min' in rule.body
    assert '25' in rule.body


def test_summer_short_fc_at_exactly_10_kwh_tomorrow():
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=18.0,
        tomorrow_pv_kwh=10.0,
        as_of=datetime(2026, 8, 25, 17, 0),
    )
    assert rule.triggered is True


def test_summer_skips_below_20_if_tomorrow_above_10():
    """Jutro >10 kWh → poczekaj na dach, nawet przy SoC 18%."""
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=18.0,
        tomorrow_pv_kwh=32.0,
        as_of=datetime(2026, 8, 25, 17, 0),
    )
    assert rule.triggered is False


def test_summer_skips_at_24_percent_even_if_tomorrow_upto_10():
    """Jutro ≤10 kWh nie spina pełnienia, gdy SoC ≥ 20%."""
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=24.0,
        tomorrow_pv_kwh=8.0,
        as_of=datetime(2026, 8, 25, 17, 0),
    )
    assert rule.triggered is False


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
