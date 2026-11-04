"""T6.2 / T6.7 — plan sterowania `evening` (B2) bez Fox API."""

from __future__ import annotations

from dataclasses import replace
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
from src.data.foxess_control import BatteryControlState, ForceChargeWindow
from src.optimization.battery_control import (
    build_plan,
    evening_apply_allowed,
    count_real_applies_today,
    evening_stop_if_due,
    morning_apply_allowed,
    compute_morning_topup,
    execute_plan,
    g12w_force_charge_windows,
    morning_cloudy_apply_trigger,
    morning_soc_floor,
    morning_topup_target_soc,
    stop_fox_quota_status,
    format_plan,
    work_mode_is_force_charge,
    load_evening_session,
    plan_and_run,
    record_evening_session_after_apply,
    save_evening_session,
    validate_apply_request,
    ControlAction,
    ControlPlan,
)


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
    fc = next(a for a in plan.actions if a.kind == 'set_force_charge_windows')
    p1, p2 = fc.params['period1'], fc.params['period2']
    assert p1.enabled and p1.start_hour == 22.0 and p1.end_hour == 1.0
    assert p2.enabled and p2.start_hour == 4.0 and p2.end_hour == 6.0


@patch('src.optimization.battery_control.FoxEssControl')
def test_execute_plan_evening_still_set_charge_when_fox_schedule_on(_fox):
    """Inc. 03.11 @22: pomijanie set_charge przy wł. harmonogramie blokowało ładowanie."""
    rule = ChargeTonightCloudyRule(
        triggered=True,
        soc_percent=10.0,
        tomorrow_pv_kwh=6.0,
        soc_below=40.0,
        weak_pv_below=12.0,
        recommendation='ŁADUJ OD 22:00 (B2 T+PV)',
        title='',
        body='',
        target_soc_percent=60.0,
        fc_minutes=51.0,
    )
    advice = _advice_evening(as_of=datetime(2026, 11, 3, 22, 0), rule=rule)
    plan = build_plan(advice)
    ctrl = _fox.return_value
    ctrl.read_state.return_value = replace(_fox_state('SelfUse'), schedule_enabled=True)
    ctrl.set_force_charge_windows.return_value = {'dry_run': False, 'action': 'set_force_charge_windows'}
    ctrl.set_work_mode.return_value = {'dry_run': False, 'action': 'set_work_mode'}
    results = execute_plan(plan, controller=ctrl, dry_run=False)
    assert ctrl.set_force_charge_windows.called
    skipped = [r for r in results if r.get('skipped')]
    assert not skipped
    assert any('set_charge i tak' in n for n in plan.notes)


@patch('src.optimization.battery_control.FoxEssControl')
def test_execute_plan_pre_cheap_skips_set_charge_when_fox_schedule_on(_fox):
    advice = _advice_evening(as_of=datetime(2026, 11, 3, 12, 0), rule=_b2_rule(triggered=False))
    advice.context = 'pre_cheap'
    plan = ControlPlan(
        context='pre_cheap',
        as_of=advice.as_of,
        recommendation='ŁADUJ 13:00–15:00 (G12w TANIO)',
        actions=[
            ControlAction(
                'set_force_charge_windows',
                'test',
                {
                    'period1': ForceChargeWindow(True, 22.0, 6.0),
                    'period2': ForceChargeWindow(True, 13.0, 15.0),
                },
            ),
        ],
        notes=[],
        dry_run=False,
    )
    ctrl = _fox.return_value
    ctrl.read_state.return_value = replace(_fox_state('SelfUse'), schedule_enabled=True)
    results = execute_plan(plan, controller=ctrl, dry_run=False)
    assert not ctrl.set_force_charge_windows.called
    assert any(r.get('skipped') for r in results)


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


def test_validate_apply_evening_denies_peak_zone():
    rule = ChargeTonightCloudyRule(
        triggered=True,
        soc_percent=43.0,
        tomorrow_pv_kwh=11.0,
        soc_below=40.0,
        weak_pv_below=12.0,
        recommendation='ŁADUJ OD 22:00 (B2 T+PV)',
        title='',
        body='',
        fc_minutes=30.0,
    )
    advice = _advice_evening(as_of=datetime(2026, 11, 3, 21, 15), rule=rule)
    assert validate_apply_request('evening', advice, phase='apply') is not None


def test_validate_apply_evening_allows_at_22_when_triggered():
    rule = ChargeTonightCloudyRule(
        triggered=True,
        soc_percent=43.0,
        tomorrow_pv_kwh=11.0,
        soc_below=40.0,
        weak_pv_below=12.0,
        recommendation='ŁADUJ OD 22:00 (B2 T+PV)',
        title='',
        body='',
        fc_minutes=30.0,
    )
    advice = _advice_evening(as_of=datetime(2026, 11, 3, 22, 1), rule=rule)
    assert validate_apply_request('evening', advice, phase='apply') is None


def _b2_rule(*, triggered: bool) -> ChargeTonightCloudyRule:
    return ChargeTonightCloudyRule(
        triggered=triggered,
        soc_percent=43.0,
        tomorrow_pv_kwh=11.0,
        soc_below=40.0,
        weak_pv_below=12.0,
        recommendation='ŁADUJ OD 22:00 (B2 T+PV)' if triggered else '',
        title='',
        body='',
        fc_minutes=30.0 if triggered else None,
    )


def _advice_morning(
    *,
    as_of: datetime,
    recommendation: str = 'ŁADUJ Z SIECI (TANIO)',
    morning_pv: float = 4.0,
) -> BatteryAdvice:
    return BatteryAdvice(
        context='morning',
        as_of=as_of,
        target_day=as_of.date().isoformat(),
        season='winter',
        tariff_zone=2,
        tariff_label='tanio (pozaszczyt)',
        snapshot=BatterySnapshot(None, 35.0, None, None, None, None),
        pv=PvOutlook(
            sunrise_hour=7.0,
            first_production_hour=9,
            morning_forecast_kwh=morning_pv,
            window_forecast_kwh=2.0,
            remaining_forecast_kwh=3.0,
            actual_so_far_kwh=0.0,
        ),
        resilience=None,
        recommendation=recommendation,
        action='test',
        details=[],
        charge_tonight=None,
    )


def test_validate_apply_evening_only_blocks_morning_when_morning_off(monkeypatch):
    monkeypatch.delenv('FOXESS_SYNC_DISABLED', raising=False)
    monkeypatch.setenv('BATTERY_CONTROL_EVENING_ONLY', '1')
    monkeypatch.setenv('BATTERY_CONTROL_MORNING_CLOUDY', '0')
    advice = _advice_morning(as_of=datetime(2026, 11, 3, 5, 0))
    reason = validate_apply_request('morning', advice, phase='apply')
    assert reason is not None
    assert 'MORNING_CLOUDY' in reason


def test_validate_apply_morning_cloudy_ok(monkeypatch):
    monkeypatch.delenv('FOXESS_SYNC_DISABLED', raising=False)
    monkeypatch.setenv('BATTERY_CONTROL_MORNING_CLOUDY', '1')
    advice = _advice_morning(as_of=datetime(2026, 11, 3, 5, 0), morning_pv=3.0)
    with patch(
        'src.optimization.battery_advisor.get_day_pv_forecast_sum',
        return_value=5.0,
    ):
        reason = validate_apply_request('morning', advice, phase='apply')
    assert reason is None


def test_morning_apply_allowed_before_six_only():
    assert morning_apply_allowed(datetime(2026, 11, 3, 5, 30)) is True
    assert morning_apply_allowed(datetime(2026, 11, 3, 6, 0)) is False


def test_morning_cloudy_trigger_skips_when_pv_high():
    advice = _advice_morning(
        as_of=datetime(2026, 11, 3, 5, 0),
        recommendation='SOC OK',
        morning_pv=15.0,
    )
    with patch(
        'src.optimization.battery_advisor.get_day_pv_forecast_sum',
        return_value=20.0,
    ):
        assert morning_cloudy_apply_trigger(advice) is False


def test_morning_cloudy_trigger_on_rezerwa_when_soc_low():
    advice = _advice_morning(
        as_of=datetime(2026, 11, 3, 5, 0),
        recommendation='ZIMNO + WYSOKI LOAD — REZERWA',
        morning_pv=3.0,
    )
    with patch(
        'src.optimization.battery_advisor.get_day_pv_forecast_sum',
        return_value=4.0,
    ):
        assert morning_cloudy_apply_trigger(advice) is True


def test_morning_topup_skips_when_soc_at_floor():
    advice = _advice_morning(
        as_of=datetime(2026, 11, 3, 5, 0),
        morning_pv=3.0,
    )
    advice.snapshot = BatterySnapshot(None, morning_soc_floor(), None, None, None, None)
    with patch(
        'src.optimization.battery_advisor.get_day_pv_forecast_sum',
        return_value=4.0,
    ):
        assert compute_morning_topup(advice) is None


def test_morning_topup_half_battery_to_ninety_at_0400():
    advice = _advice_morning(
        as_of=datetime(2026, 11, 3, 4, 0),
        recommendation='ZIMNO + WYSOKI LOAD — REZERWA',
        morning_pv=3.0,
    )
    advice.snapshot = BatterySnapshot(None, 50.0, None, None, None, None)
    with patch(
        'src.optimization.battery_advisor.get_day_pv_forecast_sum',
        return_value=4.0,
    ):
        topup = compute_morning_topup(advice)
    assert topup is not None
    assert topup.target_soc == morning_topup_target_soc()
    assert topup.fc_minutes == 24.0
    assert topup.stop_at == datetime(2026, 11, 3, 4, 24)


def test_build_plan_morning_rezerwa_starts_force_charge():
    advice = _advice_morning(
        as_of=datetime(2026, 11, 3, 4, 0),
        recommendation='ZIMNO + WYSOKI LOAD — REZERWA',
        morning_pv=3.0,
    )
    advice.snapshot = BatterySnapshot(None, 50.0, None, None, None, None)
    with patch(
        'src.optimization.battery_advisor.get_day_pv_forecast_sum',
        return_value=4.0,
    ):
        plan = build_plan(advice)
    kinds = [a.kind for a in plan.actions]
    assert 'set_work_mode' in kinds
    assert any(a.params.get('mode') == 'ForceCharge' for a in plan.actions if a.kind == 'set_work_mode')


def test_g12w_morning_fc_enables_0400_0600_window():
    p1, p2 = g12w_force_charge_windows(enabled=True)
    assert p1.enabled and p1.start_hour == 22.0 and p1.end_hour == 1.0
    assert p2.enabled and p2.start_hour == 4.0 and p2.end_hour == 6.0


def test_morning_apply_at_0400_is_cheap_and_enables_fc_window_in_plan():
    assert morning_apply_allowed(datetime(2026, 11, 3, 4, 0)) is True
    advice = _advice_morning(
        as_of=datetime(2026, 11, 3, 4, 0),
        recommendation='ZIMNO + WYSOKI LOAD — REZERWA',
        morning_pv=3.0,
    )
    advice.snapshot = BatterySnapshot(None, 50.0, None, None, None, None)
    with patch(
        'src.optimization.battery_advisor.get_day_pv_forecast_sum',
        return_value=4.0,
    ):
        plan = build_plan(advice)
    fc_action = next(a for a in plan.actions if a.kind == 'set_force_charge_windows')
    p2 = fc_action.params['period2']
    assert p2.enabled is True
    assert p2.start_hour == 4.0
    assert p2.end_hour == 6.0


def test_launchd_morning_battery_apply_runs_at_0400():
    from pathlib import Path

    plist = (
        Path(__file__).resolve().parents[1]
        / 'config/launchd/pl.smart-energy-model.morning-battery-apply.plist'
    ).read_text(encoding='utf-8')
    assert '<integer>4</integer>' in plist
    assert '<key>Hour</key>' in plist


def test_validate_apply_denies_when_b2_not_triggered(monkeypatch):
    monkeypatch.delenv('FOXESS_SYNC_DISABLED', raising=False)
    advice = _advice_evening(as_of=datetime(2026, 11, 3, 22, 5), rule=_b2_rule(triggered=False))
    reason = validate_apply_request('evening', advice, phase='apply')
    assert reason is not None
    assert 'POMIŃ' in reason


def test_validate_apply_denies_when_fox_api_paused(monkeypatch):
    monkeypatch.setenv('FOXESS_SYNC_DISABLED', '1')
    advice = _advice_evening(as_of=datetime(2026, 11, 3, 22, 5), rule=_b2_rule(triggered=True))
    reason = validate_apply_request('evening', advice, phase='apply')
    assert reason is not None
    assert 'FOXESS' in reason.upper() or 'pauza' in reason.lower() or 'wyłączony' in reason.lower()


def test_count_real_applies_ignores_dry_run(tmp_path):
    log = tmp_path / 'battery_control_log.csv'
    log.write_text(
        'logged_at,dry_run,applied_count\n'
        '2026-11-03T22:00:00,False,1\n'
        '2026-11-03T22:10:00,True,1\n'
        '2026-11-02T22:00:00,False,1\n',
        encoding='utf-8',
    )
    assert count_real_applies_today(path=str(log), as_of=datetime(2026, 11, 3, 22, 30)) == 1


def test_validate_apply_denies_when_daily_cap_reached(tmp_path, monkeypatch):
    monkeypatch.delenv('FOXESS_SYNC_DISABLED', raising=False)
    monkeypatch.setenv('BATTERY_CONTROL_MAX_APPLIES_PER_DAY', '1')
    log = tmp_path / 'battery_control_log.csv'
    log.write_text(
        'logged_at,dry_run,applied_count\n2026-11-03T22:00:00,False,1\n',
        encoding='utf-8',
    )
    monkeypatch.setattr('src.optimization.battery_control.LOG_FILE', str(log))
    advice = _advice_evening(as_of=datetime(2026, 11, 3, 22, 20), rule=_b2_rule(triggered=True))
    reason = validate_apply_request('evening', advice, phase='apply')
    assert reason is not None
    assert 'Limit apply' in reason


@patch('src.optimization.battery_control.FoxEssControl')
def test_evening_stop_before_stop_at_does_not_call_fox(_fox, tmp_path, monkeypatch):
    monkeypatch.setenv('BATTERY_EVENING_SESSION_FILE', str(tmp_path / 'sess.json'))
    save_evening_session(
        {'day': '2026-11-03', 'stop_at': '2026-11-03T22:30:00', 'stop_done': False}
    )
    status, plan, results = evening_stop_if_due(dry_run=False, as_of=datetime(2026, 11, 3, 22, 10))
    assert status == 'wait'
    assert plan is None
    assert results == []
    _fox.assert_not_called()


def _fox_state(mode: str) -> BatteryControlState:
    off = ForceChargeWindow(enabled=False, start_hour=0.0, end_hour=0.0)
    return BatteryControlState(
        device_sn='TEST',
        work_mode=mode,
        force_charge_1=off,
        force_charge_2=off,
        min_soc=10.0,
        min_soc_on_grid=10.0,
        schedule_enabled=False,
    )


def test_stop_fox_quota_blocks_repeat_inside_interval():
    as_of = datetime(2026, 11, 3, 22, 40)
    sess = {'fox_stop_attempts': 1, 'fox_stop_last_at': '2026-11-03T22:35:00'}
    assert stop_fox_quota_status(sess, as_of) == 'quota_wait'
    assert stop_fox_quota_status({'fox_stop_attempts': 4}, as_of) == 'quota_stop'
    assert stop_fox_quota_status({'fox_stop_attempts': 1, 'fox_stop_last_at': '2026-11-03T22:20:00'}, as_of) is None


@patch('src.optimization.battery_control.FoxEssControl')
def test_evening_stop_second_tick_does_not_call_fox(_fox, tmp_path, monkeypatch):
    monkeypatch.setenv('BATTERY_EVENING_SESSION_FILE', str(tmp_path / 'sess.json'))
    save_evening_session(
        {'day': '2026-11-03', 'stop_at': '2026-11-03T22:30:00', 'stop_done': False}
    )
    ctrl = _fox.return_value
    ctrl.read_state.side_effect = [
        _fox_state('ForceCharge'),
        _fox_state('ForceCharge'),
        _fox_state('ForceCharge'),
    ]
    ctrl.set_work_mode.return_value = {'action': 'set_work_mode', 'dry_run': False}
    first, _, _ = evening_stop_if_due(dry_run=False, as_of=datetime(2026, 11, 3, 22, 31))
    second, _, _ = evening_stop_if_due(dry_run=False, as_of=datetime(2026, 11, 3, 22, 34))
    assert first == 'still_force_charge'
    assert second == 'quota_wait'
    assert ctrl.read_state.call_count == 3


def test_work_mode_is_force_charge():
    assert work_mode_is_force_charge('ForceCharge') is True
    assert work_mode_is_force_charge('force_charge') is True
    assert work_mode_is_force_charge('SelfUse') is False


@patch('src.optimization.battery_control.FoxEssControl')
def test_evening_stop_sends_selfuse_when_still_force_charge(_fox, tmp_path, monkeypatch):
    monkeypatch.setenv('BATTERY_EVENING_SESSION_FILE', str(tmp_path / 'sess.json'))
    save_evening_session(
        {'day': '2026-11-03', 'stop_at': '2026-11-03T22:30:00', 'stop_done': False}
    )
    ctrl = _fox.return_value
    ctrl.read_state.side_effect = [
        _fox_state('ForceCharge'),
        _fox_state('ForceCharge'),
        _fox_state('SelfUse'),
    ]
    ctrl.set_work_mode.return_value = {'action': 'set_work_mode', 'dry_run': False, 'mode': 'SelfUse'}
    status, plan, results = evening_stop_if_due(dry_run=False, as_of=datetime(2026, 11, 3, 22, 31))
    assert status == 'stopped'
    ctrl.set_work_mode.assert_called_once_with('SelfUse', dry_run=False, force=0)
    assert plan is not None
    assert results
    assert load_evening_session()['stop_done'] is True
    assert load_evening_session()['verified_mode'] == 'SelfUse'


@patch('src.optimization.battery_control.FoxEssControl')
def test_evening_stop_retries_when_fox_stays_force_charge(_fox, tmp_path, monkeypatch):
    monkeypatch.setenv('BATTERY_EVENING_SESSION_FILE', str(tmp_path / 'sess.json'))
    save_evening_session(
        {'day': '2026-11-03', 'stop_at': '2026-11-03T22:30:00', 'stop_done': False}
    )
    ctrl = _fox.return_value
    ctrl.read_state.return_value = _fox_state('ForceCharge')
    ctrl.set_work_mode.return_value = {'action': 'set_work_mode', 'dry_run': False, 'mode': 'SelfUse'}
    status, plan, _results = evening_stop_if_due(dry_run=False, as_of=datetime(2026, 11, 3, 22, 35))
    assert status == 'still_force_charge'
    ctrl.set_work_mode.assert_called_once()
    assert plan is not None
    assert load_evening_session()['stop_done'] is False


@patch('src.optimization.battery_control.FoxEssControl')
def test_evening_stop_skips_command_when_already_selfuse(_fox, tmp_path, monkeypatch):
    monkeypatch.setenv('BATTERY_EVENING_SESSION_FILE', str(tmp_path / 'sess.json'))
    save_evening_session(
        {'day': '2026-11-03', 'stop_at': '2026-11-03T22:30:00', 'stop_done': False}
    )
    _fox.return_value.read_state.return_value = _fox_state('SelfUse')
    status, plan, _results = evening_stop_if_due(dry_run=False, as_of=datetime(2026, 11, 3, 22, 40))
    assert status == 'already_off'
    assert plan is None
    _fox.return_value.set_work_mode.assert_not_called()
    assert load_evening_session()['stop_done'] is True


@patch('src.optimization.battery_control.FoxEssControl')
def test_evening_stop_if_due_self_use(_fox, tmp_path, monkeypatch):
    sess_path = tmp_path / 'battery_evening_session.json'
    monkeypatch.setenv('BATTERY_EVENING_SESSION_FILE', str(sess_path))
    save_evening_session(
        {
            'day': '2026-11-03',
            'stop_at': '2026-11-03T22:30:00',
            'stop_done': False,
        }
    )
    _fox.return_value.read_state.return_value = _fox_state('ForceCharge')
    _fox.return_value.set_work_mode.return_value = {'action': 'set_work_mode', 'dry_run': True}
    status, plan, _results = evening_stop_if_due(
        dry_run=True,
        as_of=datetime(2026, 11, 3, 22, 31),
    )
    assert status == 'would_stop'
    assert plan is not None
    assert load_evening_session()['stop_done'] is False


def test_record_evening_session_after_apply(tmp_path, monkeypatch):  # sesja
    monkeypatch.setenv('BATTERY_EVENING_SESSION_FILE', str(tmp_path / 'sess.json'))
    rule = ChargeTonightCloudyRule(
        triggered=True,
        soc_percent=43.0,
        tomorrow_pv_kwh=11.0,
        soc_below=40.0,
        weak_pv_below=12.0,
        recommendation='ŁADUJ OD 22:00 (B2 T+PV)',
        title='',
        body='',
        fc_minutes=30.0,
    )
    advice = _advice_evening(as_of=datetime(2026, 11, 3, 22, 0), rule=rule)
    plan = build_plan(advice)
    plan.dry_run = False
    record_evening_session_after_apply(
        advice,
        plan,
        [{'action': 'set_work_mode', 'dry_run': False}],
    )
    sess = load_evening_session()
    assert sess is not None
    assert sess['stop_at'] == '2026-11-03T22:30:00'


def test_get_winter_night_load_stats_missing_file(tmp_path):
    from src.optimization.battery_advisor import get_winter_night_load_stats

    missing = tmp_path / 'missing-night.db'
    assert get_winter_night_load_stats(str(missing)) == (2.0, 4.0)


def test_get_winter_night_load_stats_operational_error(tmp_path):
    import sqlite3
    from src.optimization.battery_advisor import get_winter_night_load_stats

    db = tmp_path / 'empty-night.db'
    sqlite3.connect(db).close()
    assert get_winter_night_load_stats(str(db)) == (2.0, 4.0)


def test_detect_outage_last_night_missing_file(tmp_path):
    from src.optimization.battery_advisor import detect_outage_last_night

    missing = tmp_path / 'missing-outage.db'
    assert detect_outage_last_night(
        str(missing),
        reference=datetime(2026, 11, 3, 21, 15),
    ) == (False, None, None, None)


def test_detect_outage_last_night_database_error(tmp_path):
    import sqlite3
    from src.optimization.battery_advisor import detect_outage_last_night

    db = tmp_path / 'empty-outage.db'
    sqlite3.connect(db).close()
    assert detect_outage_last_night(
        str(db),
        reference=datetime(2026, 11, 3, 21, 15),
    ) == (False, None, None, None)


def test_detect_outage_last_night_operational_error(tmp_path):
    import sqlite3
    from src.optimization.battery_advisor import detect_outage_last_night

    db = tmp_path / 'empty-outage-op.db'
    sqlite3.connect(db).close()
    with patch(
        'src.optimization.battery_advisor.pd.read_sql_query',
        side_effect=sqlite3.OperationalError('no such table: foxess_data'),
    ):
        assert detect_outage_last_night(
            str(db),
            reference=datetime(2026, 11, 3, 21, 15),
        ) == (False, None, None, None)

