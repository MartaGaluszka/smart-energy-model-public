"""T4.17 — advice_events: upsert 1×/dzień/typ + list."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.db import Base
from api.models import AdviceEvent, AppUser
from api.services.advice_events import list_advice_events, record_advice_event


def _session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = Session()
    user = AppUser(email='t417@test.local', password_hash='x', is_active=True, created_at=datetime.utcnow())
    db.add(user)
    db.commit()
    db.refresh(user)
    return db, user.id


def test_record_advice_event_idempotent_per_day_type():
    db, user_id = _session()
    day = '2026-08-28'
    a = record_advice_event(
        db,
        user_id,
        event_date=day,
        advice_type='soc_reserve',
        payload_json='{"day":"2026-08-28"}',
        was_actionable=True,
    )
    b = record_advice_event(
        db,
        user_id,
        event_date=day,
        advice_type='soc_reserve',
        payload_json='{"day":"2026-08-28","soc":42}',
        was_actionable=True,
    )
    assert a.id == b.id
    assert b.payload_json == '{"day":"2026-08-28","soc":42}'
    assert db.query(AdviceEvent).filter(AdviceEvent.user_id == user_id).count() == 1
    db.close()


def test_record_advice_event_different_types_same_day():
    db, user_id = _session()
    day = '2026-08-28'
    record_advice_event(db, user_id, event_date=day, advice_type='soc_reserve')
    record_advice_event(db, user_id, event_date=day, advice_type='charge_tonight_cloudy')
    assert db.query(AdviceEvent).filter(AdviceEvent.user_id == user_id).count() == 2
    db.close()


def test_list_advice_events_date_filter():
    db, user_id = _session()
    record_advice_event(db, user_id, event_date='2026-08-01', advice_type='cheap_window')
    record_advice_event(db, user_id, event_date='2026-08-15', advice_type='soc_reserve')
    record_advice_event(db, user_id, event_date='2026-08-28', advice_type='charge_tonight_cloudy')
    rows = list_advice_events(db, user_id, from_date='2026-08-10', to_date='2026-08-20')
    assert len(rows) == 1
    assert rows[0].advice_type == 'soc_reserve'
    db.close()
