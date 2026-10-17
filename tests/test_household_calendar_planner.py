"""T4.8 / T4.9 — kalendarz kontekstowy → battery_planner + charge_tonight."""

from __future__ import annotations

from datetime import date, datetime

from api.services.battery_planner import (
    has_floor_heating,
    has_travel_mode,
    night_budget_extras_kwh,
    should_skip_fc_for_laundry,
)
from src.optimization.battery_advisor import (
    estimate_floor_heating_night_kwh,
    evaluate_charge_tonight_cloudy,
    suggested_soc_at_22_for_night_kwh,
)


def test_should_skip_fc_for_laundry_sunny_high_soc():
    assert should_skip_fc_for_laundry(
        tomorrow_types=['pranie', 'zmywarka'],
        tomorrow_pv_kwh=22.0,
        soc_percent=63.0,
    )
    assert not should_skip_fc_for_laundry(
        tomorrow_types=['pranie'],
        tomorrow_pv_kwh=10.0,
        soc_percent=63.0,
    )
    assert not should_skip_fc_for_laundry(
        tomorrow_types=['pranie'],
        tomorrow_pv_kwh=22.0,
        soc_percent=40.0,
    )
    assert not should_skip_fc_for_laundry(
        tomorrow_types=['obiad'],
        tomorrow_pv_kwh=22.0,
        soc_percent=80.0,
    )


def test_night_budget_extras_towel_heater():
    kwh = night_budget_extras_kwh(
        tonight_types=['grzejnik_lazienka'],
        tomorrow_types=['sniadanie'],
    )
    assert kwh == 0.75


def test_travel_mode_detects_wyjazd_and_ferie():
    assert has_travel_mode(['wyjazd'])
    assert has_travel_mode(['ferie'])
    assert not has_travel_mode(['pranie'])


def test_charge_tonight_laundry_skip_reason():
    """Case 15→16.10: pranie jutro + PV wysokie + SoC ≳55 → POMIŃ FC."""
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=63.0,
        tomorrow_pv_kwh=5.0,  # normalnie jesień chciałaby ładować
        tomorrow_temp_c=8.0,
        as_of=datetime(2026, 10, 15, 20, 0),
        laundry_skip=True,
    )
    assert rule.triggered is False
    assert rule.skip_reason == 'laundry_sunny'


def test_charge_tonight_towel_in_morning_buffer_body():
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=28.0,
        tomorrow_pv_kwh=20.6,
        tomorrow_temp_c=8.0,
        as_of=datetime(2026, 10, 12, 21, 0),
        towel_heater=True,
        breakfast_tomorrow=True,
    )
    assert rule.triggered is True
    assert 'BUFOR RANO' in rule.recommendation
    assert 'śniadanie, bojler, bufor, grzejnik' in rule.body
    assert '3,0 kWh' in rule.body


def test_charge_tonight_travel_skips_morning_buffer():
    """Wyjazd: łagodniejszy bufor — SoC <30% nie wymusza krótkiego FC."""
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=28.0,
        tomorrow_pv_kwh=20.6,
        tomorrow_temp_c=8.0,
        as_of=datetime(2026, 10, 12, 21, 0),
        travel_mild_buffer=True,
    )
    assert rule.triggered is False


def test_household_night_flags_unit_without_db():
    """Czyste helpery bez sesji DB."""
    assert night_budget_extras_kwh(tonight_types=[], tomorrow_types=[]) == 0.0
    assert should_skip_fc_for_laundry(
        tomorrow_types=None,
        tomorrow_pv_kwh=30.0,
        soc_percent=90.0,
    ) is False
    _ = date.today()  # smoke import


def test_estimate_floor_heating_scales_with_temp():
    assert estimate_floor_heating_night_kwh(12.0) == 0.0
    assert estimate_floor_heating_night_kwh(7.0) == 0.58
    assert estimate_floor_heating_night_kwh(4.0) == round(0.58 * 1.5, 2)
    assert estimate_floor_heating_night_kwh(1.0) == round(0.58 * 2.0, 2)
    assert estimate_floor_heating_night_kwh(-2.0) == round(0.58 * 2.5, 2)
    assert estimate_floor_heating_night_kwh(None) == round(0.58 * 2.0, 2)


def test_night_budget_extras_floor_heating():
    kwh = night_budget_extras_kwh(
        tonight_types=['podlogowka'],
        tomorrow_types=[],
        night_temp_c=4.0,
    )
    assert kwh == round(0.58 * 1.5, 2)
    assert has_floor_heating(['ogrzewanie_podlogowe'])


def test_charge_tonight_floor_heating_in_body_and_gate():
    """Podłogówka przy T~4°C → ~0,9 kWh w treści + wyzwala BUFOR przy SoC poniżej celu."""
    floor_kwh = estimate_floor_heating_night_kwh(4.0)
    night = 1.25 + 0.42 + floor_kwh  # BATTERY_MORNING_* defaults
    gate = suggested_soc_at_22_for_night_kwh(night)
    assert gate > 30.0
    # Jesień + PV ≳8 → ścieżka BUFOR RANO (nie B2 zima); SoC poniżej celu z budżetu.
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=min(35.0, gate - 2.0),
        tomorrow_pv_kwh=20.6,
        tomorrow_temp_c=4.0,
        as_of=datetime(2026, 10, 12, 21, 0),
        floor_heating=True,
        floor_heating_kwh=floor_kwh,
        breakfast_tomorrow=True,
    )
    assert rule.triggered is True
    assert 'BUFOR RANO' in rule.recommendation
    assert 'podłogówka' in rule.body
