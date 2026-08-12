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
