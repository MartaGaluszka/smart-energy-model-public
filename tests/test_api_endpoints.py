"""Testy HTTP endpointów FastAPI — health, auth, battery, simulate, forecast validation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import create_app


def test_health_returns_ok_without_auth(client):
    response = client.get('/health')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'
    assert 'version' in data
    assert 'db_ok' in data


def test_ready_meta_endpoint(client):
    response = client.get('/ready')
    assert response.status_code in (200, 503)
    data = response.json()
    assert 'db_ok' in data
    assert 'model_ok' in data
    assert 'model_path' in data


def test_battery_policy_requires_auth():
    application = create_app()
    with TestClient(application) as test_client:
        response = test_client.get('/api/v1/battery/policy')
    assert response.status_code == 401
    assert response.json()['code'] == 'NOT_AUTHENTICATED'


def test_battery_policy_automation_disabled(client, auth_headers):
    response = client.get('/api/v1/battery/policy', headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data['automation_enabled'] is False
    assert data['title']
    assert isinstance(data['reasons'], list)


def test_battery_suggestion_advise_only(client, auth_headers):
    payload = {
        'as_of': '2026-08-27T14:00:00',
        'season': 'summer',
        'season_mode': 'auto',
        'soc_now_percent': 62.0,
        'soc_min_percent': 15.0,
        'soc_reserve_percent': 15.0,
        'soc_target_percent': 80.0,
        'soc_min_evening_percent': 50.0,
        'force_charge_night_recommended': False,
        'force_charge_night_label': 'nie (lato)',
        'force_charge_afternoon_recommended': False,
        'force_charge_afternoon_label': 'opcjonalnie',
        'soc16_alert': False,
        'soc16_hour_passed': False,
        'soc16_percent': None,
        'soc16_title': None,
        'soc16_body': None,
        'recommendation': 'REŻIM LATO',
        'action': 'Rezerwa SoC 15%.',
        'automation_enabled': False,
        'note': 'Sugestia — nie wykonano automatycznie (advise-only).',
    }
    with patch('api.routers.battery._get_or_create_settings', return_value=MagicMock()), patch(
        'api.routers.battery.battery_planner.get_home_suggestion', return_value=payload
    ):
        response = client.get('/api/v1/battery/suggestion', headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data['automation_enabled'] is False
    assert data['soc_reserve_percent'] == 15.0
    assert data['soc_min_percent'] == 15.0


def test_simulate_bill_requires_auth():
    application = create_app()
    with TestClient(application) as test_client:
        response = test_client.post(
            '/api/v1/simulate/bill',
            json={'period_start': '2026-01-01', 'period_end': '2026-01-31'},
        )
    assert response.status_code == 401


def test_simulate_bill_ok_with_mock(client, auth_headers):
    payload = {
        'cost_no_pv_net_pln': 100.0,
        'cost_no_pv_gross_pln': 123.0,
        'cost_with_pv_net_pln': 80.0,
        'cost_with_pv_gross_pln': 98.4,
        'savings_net_pln': 20.0,
        'savings_gross_pln': 24.6,
        'production_kwh': 200.0,
        'import_kwh': 150.0,
        'export_kwh': 50.0,
        'self_consumed_kwh': 150.0,
        'deposit_credit_pln': None,
    }
    with patch('api.routers.simulate.bill_simulator.simulate_bill', return_value=payload):
        response = client.post(
            '/api/v1/simulate/bill',
            headers=auth_headers,
            json={'period_start': '2026-01-01', 'period_end': '2026-01-31'},
        )
    assert response.status_code == 200
    assert response.json()['savings_net_pln'] == 20.0


def test_forecast_validation_requires_auth():
    application = create_app()
    with TestClient(application) as test_client:
        response = test_client.get('/api/v1/forecast/validation')
    assert response.status_code == 401
