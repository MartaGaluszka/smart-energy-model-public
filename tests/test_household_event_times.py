"""Rytm domu: początek, czas programu i planowana godzina AGD (PATCH /household/events/{id})."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.db import Base
from api.deps import get_db
from api.models import AppUser

EVENTS = '/api/v1/household/events'


@pytest.fixture
def household_db(app, tmp_path):
    """Tymczasowa baza — testy nie dotykają konta w data/energy_model.db."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'household.db'}",
        connect_args={'check_same_thread': False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with Session() as seed:
        seed.add(AppUser(id=1, email='rytm@example.com', password_hash='x', is_active=True))
        seed.commit()

    def _db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    return Session


def _create(client, auth_headers, **extra):
    body = {'event_date': '2026-11-09', 'event_type': 'zmywarka', 'impact': 'up', **extra}
    response = client.post(EVENTS, json=body, headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_event_without_times_has_empty_time_fields(client, auth_headers, household_db):
    row = _create(client, auth_headers)
    assert row['start_time'] is None
    assert row['duration_min'] is None
    assert row['planned_time'] is None


def test_create_event_with_start_and_duration(client, auth_headers, household_db):
    row = _create(client, auth_headers, start_time='10:47', duration_min=138)
    assert row['start_time'] == '10:47'
    assert row['duration_min'] == 138
    listed = client.get(f'{EVENTS}?from=2026-11-09&to=2026-11-09', headers=auth_headers).json()
    assert listed[0]['start_time'] == '10:47'
    assert listed[0]['duration_min'] == 138


def test_patch_sets_start_and_duration_later(client, auth_headers, household_db):
    row = _create(client, auth_headers)
    response = client.patch(
        f"{EVENTS}/{row['id']}",
        json={'start_time': '13:32', 'duration_min': 127},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['start_time'] == '13:32'
    assert data['duration_min'] == 127
    assert data['event_type'] == 'zmywarka'


def test_patch_changes_only_sent_fields(client, auth_headers, household_db):
    row = _create(client, auth_headers, start_time='10:47', duration_min=138)
    response = client.patch(f"{EVENTS}/{row['id']}", json={'planned_time': '18:00'}, headers=auth_headers)
    data = response.json()
    assert data['planned_time'] == '18:00'
    assert data['start_time'] == '10:47'
    assert data['duration_min'] == 138


def test_patch_null_clears_field(client, auth_headers, household_db):
    row = _create(client, auth_headers, planned_time='18:00')
    response = client.patch(f"{EVENTS}/{row['id']}", json={'planned_time': None}, headers=auth_headers)
    assert response.json()['planned_time'] is None


@pytest.mark.parametrize(
    'payload',
    [
        {'start_time': '25:00'},
        {'start_time': '9:5'},
        {'planned_time': 'rano'},
        {'duration_min': 0},
        {'duration_min': -5},
        {'duration_min': 24 * 60 + 1},
    ],
)
def test_patch_rejects_bad_values(client, auth_headers, household_db, payload):
    row = _create(client, auth_headers)
    response = client.patch(f"{EVENTS}/{row['id']}", json=payload, headers=auth_headers)
    assert response.status_code == 422


def test_patch_unknown_event_is_404(client, auth_headers, household_db):
    response = client.patch(f'{EVENTS}/9999', json={'start_time': '10:00'}, headers=auth_headers)
    assert response.status_code == 404
