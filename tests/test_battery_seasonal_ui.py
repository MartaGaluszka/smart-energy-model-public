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
    assert 'charge_when_summary' in fb
    assert fb['fc_max_minutes'] == 15.0
    assert fb['fc_night_start_hour'] == 22

    live = get_home_suggestion(row, as_of=datetime(2026, 8, 27, 15, 0))
    assert live['season'] == 'summer'
    assert live['automation_enabled'] is False
    assert 'charge_when_summary' in live


def test_g12w_schedule_template_seasonal():
    from api.services.battery_planner import (
        SCHEDULE_MAX_WINDOWS,
        g12w_schedule_template,
        normalize_schedule_windows,
        schedule_template_for_tariff,
    )

    g11 = schedule_template_for_tariff('g11', night_start_hour=22, night_minutes=15)
    assert len(g11) == 1
    assert g11[0]['mode'] == 'ForceCharge'
    assert g11[0]['enabled'] is False

    g12 = schedule_template_for_tariff('g12w', night_start_hour=22, night_minutes=30)
    assert 4 <= len(g12) <= SCHEDULE_MAX_WINDOWS
    assert g12[0]['start'] == '06:00'
    assert g12[-2]['start'] == '22:00' and g12[-2]['end'] == '01:00'
    assert g12[-1]['start'] == '04:00' and g12[-1]['end'] == '06:00'
    assert all(w['enabled'] is False for w in g12)

    g13 = schedule_template_for_tariff('g13', night_start_hour=22, night_minutes=30)
    assert len(g13) > len(g12)
    assert len(g13) <= SCHEDULE_MAX_WINDOWS
    assert g13[0]['start'] == '06:00'
    assert g13[-2]['start'] == '22:00' and g13[-2]['end'] == '01:00'
    assert g13[-1]['start'] == '04:00' and g13[-1]['end'] == '06:00'

    # Kompatybilność: sezon ≠ zima → jak G11 (1 blok)
    summer = g12w_schedule_template(night_start_hour=22, night_minutes=15, season='summer')
    assert len(summer) == 1

    too_many = [
        {'start': f'{h:02d}:00', 'end': f'{(h + 1) % 24:02d}:00', 'mode': 'SelfUse'} for h in range(12)
    ]
    assert len(normalize_schedule_windows(too_many)) == SCHEDULE_MAX_WINDOWS
    assert all(w['enabled'] is False for w in normalize_schedule_windows(too_many))


def test_normalize_rejects_bad_mode():
    from api.services.battery_planner import normalize_schedule_windows

    rows = normalize_schedule_windows(
        [{'start': '13:00', 'end': '14:00', 'mode': 'Nope', 'enabled': True}]
    )
    assert rows[0]['mode'] == 'SelfUse'


def test_effective_fc_max_auto_winter_uses_recommended():
    from api.services.battery_planner import effective_fc_max, recommended_fc_max_minutes_for

    assert recommended_fc_max_minutes_for('summer') == 15.0
    assert recommended_fc_max_minutes_for('autumn') == 45.0
    assert recommended_fc_max_minutes_for('winter') == 90.0
    row = SimpleNamespace(season='auto', fc_max_minutes=15.0)
    assert effective_fc_max(row, 'winter') == 90.0
    assert effective_fc_max(row, 'autumn') == 45.0
    assert effective_fc_max(row, 'summer') == 15.0
    custom = SimpleNamespace(season='auto', fc_max_minutes=30.0)
    assert effective_fc_max(custom, 'winter') == 30.0


def test_summer_fc_respects_user_minutes_and_start_hour():
    from src.optimization.battery_advisor import evaluate_charge_tonight_cloudy

    rule = evaluate_charge_tonight_cloudy(
        soc_percent=10.0,
        tomorrow_pv_kwh=5.0,
        as_of=datetime(2026, 8, 27, 18, 0),
        fc_max_minutes=10.0,
        night_start_hour=21,
    )
    assert rule.triggered is True
    assert rule.fc_minutes == 10.0
    assert '21:00' in rule.body
    assert '21:10' in rule.body


def test_autumn_fc_caps_to_user_max_minutes():
    from src.optimization.battery_advisor import evaluate_charge_tonight_cloudy, fc_minutes_for_delta_soc

    # SoC 20 → cel ~85 = 65 pp ≈ 39 min; cap 15 → krócej
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=20.0,
        tomorrow_pv_kwh=4.0,
        as_of=datetime(2026, 10, 15, 18, 0),
        fc_max_minutes=15.0,
        night_start_hour=22,
    )
    assert rule.triggered is True
    assert rule.fc_minutes == 15.0
    assert rule.fc_minutes < fc_minutes_for_delta_soc(65.0)


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


def test_winter_afternoon_fc_triggers_cold_weak_pv():
    from src.optimization.battery_advisor import evaluate_winter_afternoon_fc

    rule = evaluate_winter_afternoon_fc(
        soc_percent=15.0,
        today_pv_kwh=3.0,
        today_temp_c=-2.0,
        as_of=datetime(2026, 1, 14, 12, 0),  # środa
    )
    assert rule.triggered is True
    assert '13–15' in rule.body or '13:00' in rule.body


def test_winter_afternoon_fc_skips_when_soc_ok():
    from src.optimization.battery_advisor import evaluate_winter_afternoon_fc

    rule = evaluate_winter_afternoon_fc(
        soc_percent=55.0,
        today_pv_kwh=2.0,
        today_temp_c=-5.0,
        as_of=datetime(2026, 1, 14, 12, 0),
    )
    assert rule.triggered is False
    assert rule.skip_reason == 'soc_ok'


def test_winter_afternoon_fc_skips_mild_sunny():
    from src.optimization.battery_advisor import evaluate_winter_afternoon_fc

    rule = evaluate_winter_afternoon_fc(
        soc_percent=25.0,
        today_pv_kwh=18.0,
        today_temp_c=8.0,
        as_of=datetime(2026, 1, 14, 12, 0),
    )
    assert rule.triggered is False
    assert rule.skip_reason == 'covered'


# --- Plan dnia SE: szablony / tryby / toggle enabled (przyciski UI Bateria) ---


def test_schedule_modes_map_ui_buttons():
    """Segment: Doładuj z sieci / Zasilaj dom / Oddaj do sieci."""
    from api.services.battery_planner import SCHEDULE_MODES, normalize_schedule_windows

    assert SCHEDULE_MODES == frozenset({'ForceCharge', 'SelfUse', 'ForceDischarge'})
    rows = normalize_schedule_windows(
        [
            {'start': '22:00', 'end': '22:15', 'mode': 'ForceCharge', 'enabled': True},
            {'start': '06:00', 'end': '13:00', 'mode': 'SelfUse', 'enabled': False},
            {'start': '13:00', 'end': '15:00', 'mode': 'ForceDischarge', 'enabled': True},
        ]
    )
    assert [r['mode'] for r in rows] == ['ForceCharge', 'SelfUse', 'ForceDischarge']
    assert rows[0]['enabled'] is True
    assert rows[1]['enabled'] is False


def test_schedule_toggle_opt_in_default_off():
    """Brak pola enabled / nowe bloki → wyłączone (jak toggle „wyłączony”)."""
    from api.services.battery_planner import normalize_schedule_windows

    rows = normalize_schedule_windows([{'start': '22:00', 'end': '22:15', 'mode': 'ForceCharge'}])
    assert rows[0]['enabled'] is False


def test_schedule_add_remove_respects_max_8():
    from api.services.battery_planner import SCHEDULE_MAX_WINDOWS, normalize_schedule_windows

    assert SCHEDULE_MAX_WINDOWS == 8
    many = [
        {'start': f'{h:02d}:00', 'end': f'{(h + 1) % 24:02d}:00', 'mode': 'SelfUse', 'enabled': False}
        for h in range(12)
    ]
    assert len(normalize_schedule_windows(many)) == 8


def test_schedule_presets_g11_g12w_g13_counts_and_modes():
    """Przyciski szablonu G11 / G12w / G13 — liczba bloków i tryby startowe."""
    from api.services.battery_planner import schedule_template_for_tariff

    g11 = schedule_template_for_tariff('g11', night_start_hour=22, night_minutes=15)
    assert len(g11) == 1
    assert g11[0]['start'] == '22:00'
    assert g11[0]['end'] == '22:15'
    assert g11[0]['mode'] == 'ForceCharge'
    assert g11[0]['enabled'] is False

    g12 = schedule_template_for_tariff('g12w', night_start_hour=22, night_minutes=15)
    assert len(g12) == 5
    assert g12[0]['start'] == '06:00' and g12[0]['mode'] == 'SelfUse'
    assert any(w['start'] == '13:00' and w['mode'] == 'ForceCharge' for w in g12)
    assert g12[-2]['start'] == '22:00' and g12[-2]['end'] == '01:00' and g12[-2]['mode'] == 'ForceCharge'
    assert g12[-1]['start'] == '04:00' and g12[-1]['end'] == '06:00' and g12[-1]['mode'] == 'ForceCharge'
    assert all(w['enabled'] is False for w in g12)

    g13 = schedule_template_for_tariff('g13', night_start_hour=22, night_minutes=15)
    assert len(g13) == 7
    assert g13[0]['start'] == '06:00' and g13[0]['mode'] == 'SelfUse'
    assert g13[-2]['start'] == '22:00' and g13[-2]['end'] == '01:00'
    assert g13[-1]['start'] == '04:00' and g13[-1]['end'] == '06:00'
    assert all(w['enabled'] is False for w in g13)


def test_schedule_insert_night_fc_keeps_disabled():
    """Przycisk „Wstaw kalkulację…” — aktualizuje godziny 1. FC, bez auto-włączania."""
    from api.services.battery_planner import normalize_schedule_windows

    plan = normalize_schedule_windows(
        [
            {'start': '22:00', 'end': '22:15', 'mode': 'ForceCharge', 'enabled': False},
            {'start': '06:00', 'end': '13:00', 'mode': 'SelfUse', 'enabled': False},
        ]
    )
    # Symulacja syncNightIntoSchedule: pierwsze ForceCharge → nowe godziny, enabled=False
    idx = next(i for i, w in enumerate(plan) if w['mode'] == 'ForceCharge')
    plan[idx] = {**plan[idx], 'start': '23:00', 'end': '00:30', 'enabled': False}
    assert plan[0]['start'] == '23:00'
    assert plan[0]['end'] == '00:30'
    assert plan[0]['enabled'] is False


def test_apply_settings_update_persists_schedule_and_preset():
    from api.services.battery_planner import apply_settings_update, schedule_windows_from_settings

    row = SimpleNamespace(
        soc_min_percent=20.0,
        schedule_windows_json=None,
        schedule_preset='g12w',
        season='auto',
        fc_max_minutes=15.0,
        fc_night_start_hour=22,
    )
    body = {
        'soc_min_percent': 20.0,
        'soc_target_percent': 80.0,
        'efficiency_pct': 93.0,
        'price_zone1': None,
        'price_zone2': None,
        'season': 'auto',
        'battery_capacity_kwh': 10.36,
        'ac_power_kw': None,
        'fc_max_minutes': 15.0,
        'fc_night_start_hour': 22,
        'schedule_preset': 'custom',
        'schedule_windows': [
            {'start': '22:00', 'end': '22:15', 'mode': 'ForceCharge', 'enabled': True},
            {'start': '06:00', 'end': '13:00', 'mode': 'Zasilaj', 'enabled': False},  # zły → SelfUse
        ],
    }
    apply_settings_update(row, dict(body))
    assert row.schedule_preset == 'custom'
    windows = schedule_windows_from_settings(row)
    assert len(windows) == 2
    assert windows[0]['enabled'] is True
    assert windows[0]['mode'] == 'ForceCharge'
    assert windows[1]['mode'] == 'SelfUse'
    assert windows[1]['enabled'] is False


def test_apply_settings_update_partial_ac_does_not_touch_season():
    from api.services.battery_planner import apply_settings_update

    row = SimpleNamespace(
        season='auto',
        soc_min_percent=20.0,
        ac_power_kw=1.2,
        schedule_windows_json='[]',
        schedule_preset='g12w',
    )
    apply_settings_update(row, {'ac_power_kw': 1.4})
    assert row.season == 'auto'
    assert row.soc_min_percent == 20.0
    assert row.ac_power_kw == 1.4
    assert row.schedule_preset == 'g12w'


def test_summer_plan_no_force_charge_when_pv_strong():
    """Lato + silne PV: bez FC 22:00 (wcześniej PV=0 → fałszywy tryb zimowy na wykresie)."""
    from api.services.battery_planner import _force_charge_hours_for_season

    strong = [0.0] * 6 + [1.5, 2.5, 3.5, 3.8, 3.5, 3.0, 2.5, 2.0, 1.5, 1.0, 0.5, 0.2] + [0.0] * 6
    assert sum(strong) > 15
    fc = _force_charge_hours_for_season(
        season='summer',
        d=date(2026, 9, 3),
        pv_forecast=strong,
        all_day_cheap=False,
    )
    assert fc == []


def test_summer_plan_night_fc_only_when_pv_weak():
    from api.services.battery_planner import _force_charge_hours_for_season

    weak = [0.2] * 24  # ~4.8 kWh
    fc = _force_charge_hours_for_season(
        season='summer',
        d=date(2026, 9, 3),  # środa — G12w noc 22–6
        pv_forecast=weak,
        all_day_cheap=False,
    )
    assert fc
    assert all(h >= 22 or h < 6 for h in fc)
    assert 13 not in fc and 14 not in fc


def test_battery_settings_put_schedule_roundtrip(client, auth_headers):
    """PUT/GET /battery/settings — toggle + tryby + preset jak w UI."""
    payload = {
        'soc_min_percent': 20,
        'soc_target_percent': 80,
        'efficiency_pct': 93,
        'season': 'auto',
        'fc_max_minutes': 15,
        'fc_night_start_hour': 22,
        'schedule_preset': 'g12w',
        'schedule_windows': [
            {'start': '22:00', 'end': '22:15', 'mode': 'ForceCharge', 'enabled': False},
            {'start': '22:15', 'end': '06:00', 'mode': 'SelfUse', 'enabled': False},
            {'start': '06:00', 'end': '13:00', 'mode': 'SelfUse', 'enabled': True},
            {'start': '13:00', 'end': '15:00', 'mode': 'ForceCharge', 'enabled': False},
            {'start': '15:00', 'end': '22:00', 'mode': 'ForceDischarge', 'enabled': False},
        ],
    }
    put = client.put('/api/v1/battery/settings', json=payload, headers=auth_headers)
    assert put.status_code == 200, put.text
    data = put.json()
    assert data['schedule_preset'] == 'g12w'
    assert len(data['schedule_windows']) == 5
    assert data['schedule_windows'][0]['mode'] == 'ForceCharge'
    assert data['schedule_windows'][0]['enabled'] is False
    assert data['schedule_windows'][2]['enabled'] is True
    assert data['schedule_windows'][4]['mode'] == 'ForceDischarge'

    get = client.get('/api/v1/battery/settings', headers=auth_headers)
    assert get.status_code == 200
    again = get.json()
    assert again['schedule_windows'][2]['start'] == '06:00'
    assert again['schedule_windows'][2]['enabled'] is True
    assert again['schedule_max_windows'] == 8
