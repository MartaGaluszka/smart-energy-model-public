"""Regresja: KPI wykresu Prognoza vs partial midday CSV (12.09 bez Porannej)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from api.services.forecast_ml import _archived_hourly_predictions, get_hourly_forecast


def test_archived_hourly_does_not_fallback_to_partial_midday():
    """Midday ma 9h model-only (~7 kWh) — nie używamy tego jako pełnej doby."""
    partial = pd.DataFrame({
        'day': ['2026-09-12'] * 9,
        'hour': [7, 12, 13, 14, 15, 16, 17, 18, 19],
        'predicted_kwh': [1.0, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5],
        'prediction_source': ['model'] * 9,
    })
    with patch('src.models.forecast_validation.load_forecast_snapshot') as load:
        load.side_effect = [
            (pd.DataFrame(), None),  # daily — brak
            (partial, pd.Timestamp('2026-09-12 12:00:38')),
            (pd.DataFrame(), None),
            (pd.DataFrame(), None),
        ]
        out = _archived_hourly_predictions('2026-09-12')
    assert out.empty


def test_past_day_without_daily_scales_to_official_outlook():
    """Gdy brak Porannej: suma KPI = peak/midday z forecast_history, nie suma CSV."""
    replay = pd.DataFrame({
        'day': ['2026-09-12'] * 3,
        'hour': [10, 11, 12],
        'predicted_kwh': [4.0, 4.0, 4.0],
        'prediction_source': ['model'] * 3,
    })
    predictor = MagicMock()
    predictor.model_path = 'models/test.joblib'
    predictor.predict_days.return_value = replay

    with patch('api.services.forecast_ml._archived_hourly_predictions', return_value=pd.DataFrame()), \
         patch('src.models.forecast_validation.official_day_outlook_total', return_value=11.94), \
         patch('src.models.forecast_validation.get_actual_hourly_ml', return_value=pd.DataFrame()):
        payload = get_hourly_forecast(predictor, '2026-09-12')

    assert payload['total_kwh'] == 11.94
    assert abs(sum(h['predicted_kwh'] for h in payload['hours']) - 11.94) < 0.01
