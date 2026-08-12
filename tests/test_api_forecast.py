"""Testy HTTP endpointu prognozy godzinowej (FastAPI /api/v1/forecast/hourly)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_forecast_hourly_requires_auth():
    from fastapi.testclient import TestClient

    from api.main import create_app

    application = create_app()
    with TestClient(application) as test_client:
        response = test_client.get('/api/v1/forecast/hourly')
    assert response.status_code == 401
    assert response.json()['code'] == 'NOT_AUTHENTICATED'


def test_forecast_hourly_model_not_loaded(client, app):
    app.state.pv_predictor = None
    response = client.get(
        '/api/v1/forecast/hourly',
        headers={'Authorization': 'Bearer test-token'},
    )
    assert response.status_code == 503
    assert response.json()['code'] == 'MODEL_NOT_LOADED'


def test_forecast_hourly_ok(client, app):
    mock_predictor = MagicMock()
    mock_predictor.model_path = 'models/test.joblib'
    app.state.pv_predictor = mock_predictor

    payload = {
        'day': '2026-08-06',
        'hours': [{
            'hour': 12,
            'predicted_kwh': 2.5,
            'prediction_source': 'model',
            'actual_kwh': None,
            'error_pct': None,
        }],
        'total_kwh': 18.0,
        'model_path': 'models/test.joblib',
    }

    with patch('api.routers.forecast.forecast_ml.get_hourly_forecast', return_value=payload):
        response = client.get(
            '/api/v1/forecast/hourly?day=2026-08-06',
            headers={'Authorization': 'Bearer test-token'},
        )

    assert response.status_code == 200
    data = response.json()
    assert data['day'] == '2026-08-06'
    assert data['total_kwh'] == 18.0
    assert len(data['hours']) == 1
    assert data['hours'][0]['hour'] == 12
