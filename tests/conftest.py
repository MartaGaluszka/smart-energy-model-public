"""Wspólne fixture'y pytest dla testów API."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.deps import get_current_user
from api.main import create_app

# Skrypty integracyjne (uruchamiane ręcznie, nie przez pytest collect)
collect_ignore = ['test_pv_pipeline_smoke.py', 'test_dual_and_ukmo.py']


@pytest.fixture
def app():
    application = create_app()
    application.dependency_overrides[get_current_user] = lambda: MagicMock(id=1, is_active=True)
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers():
    return {'Authorization': 'Bearer test-token'}


@pytest.fixture(autouse=True)
def _disable_fox_battery_mirror_in_tests(monkeypatch):
    """Testy API nie wołają live FoxESS przy GET/PUT /battery/settings."""

    def _merge(payload, persist_row=None):
        out = dict(payload)
        out.setdefault('schedule_source', 'database')
        out['fox_mirror'] = {'ok': False, 'error': 'disabled in tests'}
        return out

    monkeypatch.setattr(
        'api.services.foxess_battery_mirror.merge_fox_into_settings_payload',
        _merge,
    )
    monkeypatch.setattr(
        'api.services.foxess_battery_mirror.read_fox_battery_mirror',
        lambda: {'ok': False, 'error': 'disabled in tests', 'schedule_windows': []},
    )
    monkeypatch.setattr(
        'api.services.foxess_battery_mirror.push_schedule_windows_to_fox',
        lambda *a, **k: {'ok': True, 'groups_sent': 0},
    )
