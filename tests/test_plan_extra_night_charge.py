"""Plan jutra z aplikacji (godziny AGD, obiad) → budżet nocnego ładowania baterii."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.db import Base
from api.models import AppUser, HouseholdEvent
from api.services import battery_planner
from api.services.battery_planner import (
    events_with_times_for_day,
    household_night_flags,
    plan_extra_from_events,
    plan_note_text,
)
from src.optimization.battery_advisor import evaluate_charge_tonight_cloudy

# Jutro słabe: ~8 kWh, produkcja rusza ok. 8:00 (kształt jak prognoza na 10.11).
WEAK_HOURLY = {7: 0.4, 8: 0.9, 9: 1.6, 10: 2.2, 11: 1.3, 12: 0.8, 13: 0.4, 14: 0.1}
# Jutro słoneczne: ~22 kWh, mocny start od 8:00.
SUNNY_HOURLY = {7: 0.5, 8: 1.8, 9: 3.0, 10: 3.8, 11: 3.8, 12: 3.6, 13: 3.0, 14: 1.5, 15: 0.5}


def test_weak_day_counts_until_13_plus_lunch_reserve():
    plan = plan_extra_from_events(
        [('zmywarka', '09:00'), ('suszarka', '15:00'), ('pranie', None), ('sniadanie', '08:00')],
        pv_hourly=WEAK_HOURLY,
        day_pv_kwh=8.2,
    )
    assert plan['mode'] == 'weak'
    # zmywarka 1,2 + zapas na obiad 2,2; suszarka po 13:00 i pranie bez godziny nie wchodzą.
    assert plan['kwh'] == pytest.approx(3.4)
    assert [i[0] for i in plan['items']] == ['zmywarka', 'obiad']


def test_weak_day_lunch_counts_even_when_planned_after_13():
    plan = plan_extra_from_events([('obiad', '14:00')], pv_hourly=WEAK_HOURLY, day_pv_kwh=8.2)
    assert plan['kwh'] == pytest.approx(2.2)
    assert len(plan['items']) == 1


def test_sunny_day_counts_only_before_pv_start_and_no_lunch():
    plan = plan_extra_from_events(
        [('zmywarka', '07:00'), ('zmywarka', '10:00'), ('obiad', '12:30'), ('pranie', None)],
        pv_hourly=SUNNY_HOURLY,
        day_pv_kwh=22.0,
    )
    assert plan['mode'] == 'sunny'
    assert plan['pv_start_hour'] == 8
    assert plan['kwh'] == pytest.approx(1.2)  # tylko zmywarka 7:00


def test_unknown_pv_adds_nothing():
    plan = plan_extra_from_events([('obiad', '12:00')], pv_hourly=None, day_pv_kwh=None)
    assert plan['kwh'] == 0.0


def test_ignored_types_do_not_count():
    plan = plan_extra_from_events(
        [('mac_mini', '07:00'), ('podlogowka', '06:00'), ('kolacja', '07:00'), ('przetwory', '08:00')],
        pv_hourly=WEAK_HOURLY,
        day_pv_kwh=8.2,
    )
    assert [i[0] for i in plan['items']] == ['obiad']  # tylko domyślny zapas na obiad


def test_plan_note_mentions_scope_and_items():
    weak = plan_extra_from_events([('zmywarka', '09:00')], pv_hourly=WEAK_HOURLY, day_pv_kwh=8.2)
    note = plan_note_text(weak)
    assert 'do 13:00' in note and 'obiad' in note and 'zmywarka 09:00' in note and '3,4 kWh' in note
    sunny = plan_extra_from_events([('zmywarka', '07:00')], pv_hourly=SUNNY_HOURLY, day_pv_kwh=22.0)
    assert 'do startu produkcji ok. 8:00' in plan_note_text(sunny)
    assert plan_note_text({'kwh': 0.0}) == ''


def _rule(**extra):
    return evaluate_charge_tonight_cloudy(
        soc_percent=50.0,
        tomorrow_pv_kwh=8.2,
        tomorrow_temp_c=6.0,
        as_of=datetime(2026, 11, 9, 21, 30),
        capacity_kwh=10.0,
        **extra,
    )


def test_plan_raises_night_target_soc_on_weak_day():
    base = _rule()
    with_plan = _rule(plan_extra_kwh=0.5, plan_note='Plan na jutro: test.')
    assert base.triggered and with_plan.triggered
    assert with_plan.target_soc_percent >= base.target_soc_percent
    assert with_plan.plan_extra_kwh == pytest.approx(0.5)
    assert with_plan.body.endswith('Plan na jutro: test.')


def test_plan_target_is_capped(monkeypatch):
    monkeypatch.setenv('BATTERY_PLAN_TARGET_MAX_SOC', '85')
    rule = _rule(plan_extra_kwh=5.0)
    assert rule.target_soc_percent <= 85.0 or rule.target_soc_percent == _rule().target_soc_percent


def test_plan_raises_target_on_sunny_day_headroom():
    """Słoneczny jutro: baza = 70%; zmywarka 7:00 podnosi cel o jej kWh."""
    kwargs = dict(
        soc_percent=40.0,
        tomorrow_pv_kwh=22.0,
        tomorrow_temp_c=6.0,
        as_of=datetime(2026, 11, 9, 21, 30),
        capacity_kwh=10.0,
    )
    base = evaluate_charge_tonight_cloudy(**kwargs)
    with_plan = evaluate_charge_tonight_cloudy(plan_extra_kwh=1.2, **kwargs)
    assert base.triggered and with_plan.triggered
    assert with_plan.target_soc_percent == pytest.approx(base.target_soc_percent + 12.0)


def test_no_plan_keeps_previous_behaviour():
    assert _rule().plan_extra_kwh is None
    assert _rule(plan_extra_kwh=0.0).plan_extra_kwh is None


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'plan.db'}", connect_args={'check_same_thread': False}, future=True
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with Session() as db:
        db.add(AppUser(id=1, email='plan@example.com', password_hash='x', is_active=True))
        db.commit()
        yield db


def _add(db, day, etype, **kw):
    db.add(HouseholdEvent(user_id=1, event_date=day, event_type=etype, impact='up', **kw))
    db.commit()


def test_events_with_times_uses_start_then_planned(db_session):
    _add(db_session, '2026-11-10', 'zmywarka', planned_time='09:00')
    _add(db_session, '2026-11-10', 'pranie', start_time='07:30')
    _add(db_session, '2026-11-10', 'obiad')
    got = dict(events_with_times_for_day(db_session, 1, date(2026, 11, 10)))
    assert got == {'zmywarka': '09:00', 'pranie': '07:30', 'obiad': None}


def test_household_night_flags_adds_plan(db_session, monkeypatch):
    _add(db_session, '2026-11-10', 'zmywarka', planned_time='09:00')
    monkeypatch.setattr(
        'src.optimization.battery_advisor.get_day_pv_hourly_kwh',
        lambda *a, **k: WEAK_HOURLY,
    )
    flags = household_night_flags(
        db_session, 1, datetime(2026, 11, 9, 21, 30), tomorrow_pv_kwh=8.2, soc_percent=50.0, night_temp_c=6.0
    )
    assert flags['plan_extra_kwh'] == pytest.approx(3.4)
    assert 'zmywarka 09:00' in flags['plan_note']


def test_travel_ignores_plan(db_session, monkeypatch):
    _add(db_session, '2026-11-10', 'wyjazd')
    _add(db_session, '2026-11-10', 'zmywarka', planned_time='09:00')
    monkeypatch.setattr(
        'src.optimization.battery_advisor.get_day_pv_hourly_kwh',
        lambda *a, **k: WEAK_HOURLY,
    )
    flags = household_night_flags(
        db_session, 1, datetime(2026, 11, 9, 21, 30), tomorrow_pv_kwh=8.2, soc_percent=50.0, night_temp_c=6.0
    )
    assert flags['plan_extra_kwh'] == 0.0
    assert flags['plan_note'] == ''


def test_battery_planner_exports_plan_constants():
    assert battery_planner.PLAN_CLOUDY_HORIZON_HOUR == 13
