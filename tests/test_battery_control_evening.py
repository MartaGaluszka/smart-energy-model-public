"""T6.2 / T6.7 — plan sterowania `evening` (B2) bez Fox API."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from src.optimization.battery_advisor import (
    BatteryAdvice,
    BatterySnapshot,
    ChargeTonightCloudyRule,
    PvOutlook,
    advise,
)
from src.optimization.battery_advisor import format_advice
from src.optimization.battery_control import build_plan, evening_apply_allowed, format_plan, plan_and_run


def _pv() -> PvOutlook:
    return PvOutlook(
        sunrise_hour=7.0,
        first_production_hour=8,
        morning_forecast_kwh=5.0,
        window_forecast_kwh=3.0,
        remaining_forecast_kwh=2.0,
        actual_so_far_kwh=1.0,
    )


def _advice_evening(
    *,
    as_of: datetime,
    rule: ChargeTonightCloudyRule | None,
    recommendation: str = '',
) -> BatteryAdvice:
    rec = recommendation or (rule.recommendation if rule and rule.triggered else 'POMIŃ NOCNE FC (B2)')
    return BatteryAdvice(
        context='evening',
        as_of=as_of,
        target_day=as_of.date().isoformat(),
        season='winter',
        tariff_zone=1,
        tariff_label='drogo (szczyt)',
        snapshot=BatterySnapshot(None, 45.0, None, None, None, None),
        pv=_pv(),
        resilience=None,
        recommendation=rec,
        action='test',
        details=[],
        charge_tonight=rule,
    )


def test_evening_apply_allowed_only_in_cheap_zone():
    assert evening_apply_allowed(datetime(2026, 11, 3, 21, 15)) is False
    assert evening_apply_allowed(datetime(2026, 11, 3, 22, 5)) is True
    assert evening_apply_allowed(datetime(2026, 11, 1, 12, 0)) is True  # weekend cała doba tanio


def test_build_plan_evening_skip_is_noop():
    rule = ChargeTonightCloudyRule(
        triggered=False,
        soc_percent=70.0,
        tomorrow_pv_kwh=15.0,
        soc_below=40.0,
        weak_pv_below=12.0,
        recommendation='',
        title='',
        body='',
        skip_reason='Jutro dużo PV',
    )
    plan = build_plan(_advice_evening(as_of=datetime(2026, 11, 3, 21, 15), rule=rule))
    assert plan.context == 'evening'
    assert len(plan.actions) == 1
    assert plan.actions[0].kind == 'noop'
    assert 'POMIŃ' in plan.actions[0].description


def test_build_plan_evening_charge_before_22_windows_only():
    rule = ChargeTonightCloudyRule(
        triggered=True,
        soc_percent=43.0,
        tomorrow_pv_kwh=11.0,
        soc_below=40.0,
        weak_pv_below=12.0,
        recommendation='ŁADUJ OD 22:00 (B2 T+PV)',
        title='',
        body='',
        target_soc_percent=90.0,
        fc_minutes=30.0,
    )
    plan = build_plan(_advice_evening(as_of=datetime(2026, 11, 3, 21, 15), rule=rule))
    kinds = [a.kind for a in plan.actions]
    assert 'set_force_charge_windows' in kinds
    assert 'set_work_mode' not in kinds
    assert any('22:00' in n for n in plan.notes)


def test_build_plan_evening_charge_at_22_includes_force_charge():
    rule = ChargeTonightCloudyRule(
        triggered=True,
        soc_percent=43.0,
        tomorrow_pv_kwh=11.0,
        soc_below=40.0,
        weak_pv_below=12.0,
        recommendation='ŁADUJ OD 22:00 (B2 T+PV)',
        title='',
        body='',
        target_soc_percent=90.0,
        fc_minutes=30.0,
    )
    plan = build_plan(_advice_evening(as_of=datetime(2026, 11, 3, 22, 2), rule=rule))
    kinds = [a.kind for a in plan.actions]
    assert kinds.count('set_force_charge_windows') == 1
    assert any(a.kind == 'set_work_mode' and a.params.get('mode') == 'ForceCharge' for a in plan.actions)
    assert any('30' in n and 'stop' in n.lower() for n in plan.notes)


@patch('src.optimization.battery_advisor.get_battery_snapshot')
@patch('src.optimization.battery_advisor.get_pv_outlook')
@patch('src.optimization.battery_advisor.get_day_pv_forecast_sum', return_value=11.0)
@patch('src.optimization.battery_advisor.get_day_mean_temp_c', return_value=2.0)
@patch('src.optimization.battery_advisor.evaluate_charge_tonight_cloudy')
def test_advise_evening_uses_b2_rule(_eval, _t, _pv_sum, _pv_out, _snap):
    _snap.return_value = BatterySnapshot(None, 43.0, None, None, None, None)
    _pv_out.return_value = _pv()
    _eval.return_value = ChargeTonightCloudyRule(
        triggered=True,
        soc_percent=43.0,
        tomorrow_pv_kwh=11.0,
        soc_below=40.0,
        weak_pv_below=12.0,
        recommendation='ŁADUJ OD 22:00 (B2 T+PV)',
        title='T',
        body='B',
        target_soc_percent=90.0,
        fc_minutes=30.0,
    )
    advice = advise('evening', as_of=datetime(2026, 11, 3, 21, 15))
    assert advice.context == 'evening'
    assert advice.charge_tonight is not None
    assert advice.charge_tonight.triggered is True
    assert advice.recommendation.startswith('ŁADUJ OD 22:00')
    _eval.assert_called_once()


@patch('src.optimization.battery_advisor.get_battery_snapshot')
@patch('src.optimization.battery_advisor.get_pv_outlook')
@patch('src.optimization.battery_advisor.get_day_pv_forecast_sum', return_value=15.0)
@patch('src.optimization.battery_advisor.get_day_mean_temp_c', return_value=5.0)
@patch('src.optimization.battery_advisor.evaluate_charge_tonight_cloudy')
def test_advise_evening_pomin_when_b2_not_triggered(_eval, _t, _pv_sum, _pv_out, _snap):
    _snap.return_value = BatterySnapshot(None, 72.0, None, None, None, None)
    _pv_out.return_value = _pv()
    _eval.return_value = ChargeTonightCloudyRule(
        triggered=False,
        soc_percent=72.0,
        tomorrow_pv_kwh=15.0,
        soc_below=40.0,
        weak_pv_below=12.0,
        recommendation='',
        title='',
        body='',
        skip_reason='Jutro dużo PV',
    )
    advice = advise('evening', as_of=datetime(2026, 11, 3, 21, 15))
    assert advice.recommendation == 'POMIŃ NOCNE FC (B2)'
    assert advice.charge_tonight is not None
    assert advice.charge_tonight.triggered is False
    assert 'Jutro dużo PV' in advice.action


def test_format_advice_and_plan_evening_labels():
    rule = ChargeTonightCloudyRule(
        triggered=True,
        soc_percent=43.0,
        tomorrow_pv_kwh=11.0,
        soc_below=40.0,
        weak_pv_below=12.0,
        recommendation='ŁADUJ OD 22:00 (B2 T+PV)',
        title='',
        body='',
        target_soc_percent=90.0,
        fc_minutes=30.0,
    )
    advice = _advice_evening(as_of=datetime(2026, 11, 3, 21, 15), rule=rule)
    plan = build_plan(advice)
    assert 'WIECZÓR' in format_advice(advice)
    rendered = format_plan(advice, plan, [])
    assert 'WIECZÓR' in rendered or 'B2' in rendered
    assert plan.context == 'evening'


@patch('src.optimization.battery_control.FoxEssControl')
@patch('src.optimization.battery_advisor.get_battery_snapshot')
@patch('src.optimization.battery_advisor.get_pv_outlook')
@patch('src.optimization.battery_advisor.get_day_pv_forecast_sum', return_value=11.0)
@patch('src.optimization.battery_advisor.get_day_mean_temp_c', return_value=2.0)
@patch('src.optimization.battery_advisor.evaluate_charge_tonight_cloudy')
def test_plan_and_run_evening_dry_run(_eval, _t, _pv_sum, _pv_out, _snap, _fox):
    _snap.return_value = BatterySnapshot(None, 43.0, None, None, None, None)
    _pv_out.return_value = _pv()
    _eval.return_value = ChargeTonightCloudyRule(
        triggered=True,
        soc_percent=43.0,
        tomorrow_pv_kwh=11.0,
        soc_below=40.0,
        weak_pv_below=12.0,
        recommendation='ŁADUJ OD 22:00 (B2 T+PV)',
        title='',
        body='',
        target_soc_percent=90.0,
        fc_minutes=30.0,
    )
    _fox.return_value.read_state.side_effect = ValueError('no fox in test')
    advice, plan, results = plan_and_run(
        'evening',
        as_of=datetime(2026, 11, 3, 21, 15),
        dry_run=True,
        read_state=True,
    )
    assert advice.context == 'evening'
    assert plan.context == 'evening'
    assert results == []
    assert any('FoxESS' in n for n in plan.notes)
