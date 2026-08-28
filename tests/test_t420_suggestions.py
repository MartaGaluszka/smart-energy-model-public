"""T4.20 — generator sugestii (cheap_window + cron helpers)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.db import Base
from api.models import AdviceEvent, AppUser, Notification
from api.services.notifications_service import (
    generate_suggestions_for_all_users,
    generate_suggestions_for_user,
    maybe_upsert_cheap_window,
    suggestion_context_for_hour,
)


def _session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = Session()
    user = AppUser(email='t420@test.local', password_hash='x', is_active=True, created_at=datetime.utcnow())
    db.add(user)
    db.commit()
    db.refresh(user)
    return db, user.id


def test_suggestion_context_for_hour():
    assert suggestion_context_for_hour(5) == 'morning'
    assert suggestion_context_for_hour(12) == 'pre_cheap'
    assert suggestion_context_for_hour(16) == 'peak'


@patch('api.services.notifications_service.maybe_upsert_soc16_reserve', return_value=None)
@patch('api.services.notifications_service.maybe_upsert_charge_tonight_cloudy', return_value=None)
def test_cheap_window_upsert_idempotent(_cloudy, _soc16):
    db, user_id = _session()

    snap = MagicMock(soc_percent=55.0)
    wait = MagicMock(
        triggered=False,
        title='',
        body='',
    )

    with (
        patch('src.optimization.battery_advisor.get_battery_snapshot', return_value=snap),
        patch('src.optimization.battery_advisor.seasonal_soc_reserve', return_value=20.0),
        patch('src.optimization.battery_advisor.evaluate_below_reserve_wait_cheap', return_value=wait),
        patch('src.optimization.battery_advisor.get_day_pv_forecast_sum', return_value=18.0),
        patch('src.optimization.battery_advisor.next_cheap_window_label', return_value='22–6'),
        patch('src.optimization.g12w_tariff.is_cheap_zone', return_value=False),
        patch('src.optimization.g12w_tariff.tariff_summary', return_value='G12w.'),
    ):
        a = maybe_upsert_cheap_window(db, user_id, 'peak')
        b = maybe_upsert_cheap_window(db, user_id, 'peak')

    assert a is not None and b is not None
    assert a.id == b.id
    assert a.notif_type == 'cheap_window'
    assert 'szczyt wieczorny' in a.title.lower() or 'Sugestia' in a.title
    assert db.query(Notification).filter(Notification.user_id == user_id).count() == 1
    assert db.query(AdviceEvent).filter(AdviceEvent.advice_type == 'cheap_window').count() == 1
    db.close()


@patch('api.services.notifications_service.maybe_upsert_soc16_reserve', return_value=None)
@patch('api.services.notifications_service.maybe_upsert_charge_tonight_cloudy', return_value=None)
def test_generate_for_all_users_counts_active(_cloudy, _soc16):
    db, user_id = _session()
    inactive = AppUser(
        email='inactive@test.local',
        password_hash='x',
        is_active=False,
        created_at=datetime.utcnow(),
    )
    db.add(inactive)
    db.commit()

    snap = MagicMock(soc_percent=60.0)
    wait = MagicMock(triggered=False, title='', body='')

    with (
        patch('src.optimization.battery_advisor.get_battery_snapshot', return_value=snap),
        patch('src.optimization.battery_advisor.seasonal_soc_reserve', return_value=20.0),
        patch('src.optimization.battery_advisor.evaluate_below_reserve_wait_cheap', return_value=wait),
        patch('src.optimization.battery_advisor.get_day_pv_forecast_sum', return_value=12.0),
        patch('src.optimization.battery_advisor.next_cheap_window_label', return_value='13–15'),
        patch('src.optimization.g12w_tariff.is_cheap_zone', return_value=False),
        patch('src.optimization.g12w_tariff.tariff_summary', return_value='G12w.'),
    ):
        summary = generate_suggestions_for_all_users(db, 'morning')

    assert summary['users'] == 1
    assert summary['cheap_window'] == 1
    assert summary['context'] == 'morning'
    # only active user
    assert db.query(Notification).count() == 1
    db.close()


def test_generate_suggestions_for_user_keys():
    db, user_id = _session()
    with (
        patch(
            'api.services.notifications_service.maybe_upsert_cheap_window',
            return_value=MagicMock(),
        ) as cheap,
        patch(
            'api.services.notifications_service.maybe_upsert_charge_tonight_cloudy',
            return_value=None,
        ),
        patch(
            'api.services.notifications_service.maybe_upsert_soc16_reserve',
            return_value=None,
        ),
    ):
        out = generate_suggestions_for_user(db, user_id, 'pre_cheap')
    cheap.assert_called_once_with(db, user_id, 'pre_cheap')
    assert out['context'] == 'pre_cheap'
    assert out['cheap_window'] is not None
    db.close()
