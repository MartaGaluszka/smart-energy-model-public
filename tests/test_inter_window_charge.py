"""Bilans ładowania między oknami G12w (PV-first)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from src.optimization.battery_advisor import BatteryAdvice, BatterySnapshot, PvOutlook, advise
from src.optimization.battery_control import (
    compute_morning_topup,
    compute_pre_cheap_topup,
    morning_cloudy_apply_trigger,
    pre_cheap_apply_trigger,
)
from src.optimization.inter_window_charge import (
    compute_inter_window_charge_plan,
    inter_window_auto_enabled,
)


def _pv() -> PvOutlook:
    return PvOutlook(
        sunrise_hour=7.0,
        first_production_hour=7,
        morning_forecast_kwh=16.0,
        window_forecast_kwh=2.0,
        remaining_forecast_kwh=8.0,
        actual_so_far_kwh=0.0,
    )


def test_inter_window_skips_when_pv_covers_load():
    as_of = datetime(2026, 11, 5, 4, 0, 0)
    with patch(
        'src.optimization.inter_window_charge._forecast_pv_kwh',
        return_value=12.0,
    ), patch(
        'src.optimization.inter_window_charge._segment_load_kwh',
        return_value=3.0,
    ):
        plan = compute_inter_window_charge_plan(
            context='morning',
            as_of=as_of,
            soc_percent=62.0,
            reserve_percent=40.0,
            season='winter',
            temp_c=5.0,
            day_pv_kwh=19.0,
        )
    assert plan.triggered is False
    assert plan.skip_reason == 'pv_covers_or_wear'


def test_inter_window_triggers_grid_charge_when_deficit():
    as_of = datetime(2026, 11, 3, 4, 0, 0)
    with patch(
        'src.optimization.inter_window_charge._forecast_pv_kwh',
        return_value=1.5,
    ), patch(
        'src.optimization.inter_window_charge._segment_load_kwh',
        return_value=9.0,
    ):
        plan = compute_inter_window_charge_plan(
            context='morning',
            as_of=as_of,
            soc_percent=25.0,
            reserve_percent=40.0,
            season='winter',
            temp_c=2.0,
            day_pv_kwh=4.0,
        )
    assert plan.triggered is True
    assert plan.grid_charge_kwh is not None
    assert plan.grid_charge_kwh >= 2.0
    assert plan.target_soc_percent is not None
    assert plan.fc_minutes is not None


def test_morning_topup_prefers_inter_window_over_legacy_sunny_skip():
    as_of = datetime(2026, 11, 3, 4, 0, 0)
    advice = BatteryAdvice(
        context='morning',
        as_of=as_of,
        target_day='2026-11-03',
        season='winter',
        tariff_zone=2,
        tariff_label='tanio',
        snapshot=BatterySnapshot(None, 25.0, None, None, None, None),
        pv=_pv(),
        resilience=None,
        recommendation='test',
        action='test',
        details=[],
    )
    with patch(
        'src.optimization.inter_window_charge._forecast_pv_kwh',
        return_value=1.5,
    ), patch(
        'src.optimization.inter_window_charge._segment_load_kwh',
        return_value=9.0,
    ):
        iw = compute_inter_window_charge_plan(
            context='morning',
            as_of=as_of,
            soc_percent=25.0,
            reserve_percent=40.0,
            season='winter',
            temp_c=2.0,
            day_pv_kwh=4.0,
        )
    with patch(
        'src.optimization.inter_window_charge.compute_inter_window_charge_plan',
        return_value=iw,
    ), patch(
        'src.optimization.battery_control._morning_pv_weak',
        return_value=False,
    ):
        advice.inter_window = iw
        top = compute_morning_topup(advice)
    assert top is not None
    assert morning_cloudy_apply_trigger(advice) is True


def test_advise_morning_includes_inter_window_details():
    as_of = datetime(2026, 11, 3, 4, 0, 0)
    with patch(
        'src.optimization.inter_window_charge._forecast_pv_kwh',
        return_value=1.0,
    ), patch(
        'src.optimization.inter_window_charge._segment_load_kwh',
        return_value=10.0,
    ), patch(
        'src.optimization.battery_advisor.get_battery_snapshot',
        return_value=BatterySnapshot('2026-11-03 04:00', 30.0, None, None, None, 0.1),
    ), patch(
        'src.optimization.battery_advisor.get_pv_outlook',
        return_value=_pv(),
    ), patch(
        'src.optimization.battery_advisor.get_day_pv_forecast_sum',
        return_value=4.0,
    ), patch(
        'src.optimization.battery_advisor.get_day_mean_temp_c',
        return_value=3.0,
    ), patch(
        'src.optimization.battery_advisor.build_resilience_outlook',
        return_value=None,
    ):
        advice = advise('morning', as_of=as_of)
    assert advice.inter_window is not None
    assert any('Bilans' in d for d in advice.details)


def test_pre_cheap_trigger_follows_inter_window():
    as_of = datetime(2026, 11, 3, 12, 0, 0)
    with patch(
        'src.optimization.inter_window_charge._forecast_pv_kwh',
        return_value=2.0,
    ), patch(
        'src.optimization.inter_window_charge._segment_load_kwh',
        return_value=8.0,
    ):
        iw = compute_inter_window_charge_plan(
            context='pre_cheap',
            as_of=as_of,
            soc_percent=35.0,
            reserve_percent=40.0,
            season='winter',
            temp_c=3.0,
            day_pv_kwh=6.0,
        )
    advice = BatteryAdvice(
        context='pre_cheap',
        as_of=as_of,
        target_day='2026-11-03',
        season='winter',
        tariff_zone=1,
        tariff_label='drogo',
        snapshot=BatterySnapshot(None, 35.0, None, None, None, None),
        pv=_pv(),
        resilience=None,
        recommendation='test',
        action='test',
        details=[],
        inter_window=iw,
    )
    if iw.triggered:
        assert pre_cheap_apply_trigger(advice) is True
        assert compute_pre_cheap_topup(advice) is not None


def test_inter_window_auto_enabled_default_on():
    with patch.dict('os.environ', {}, clear=False):
        assert inter_window_auto_enabled() is True
