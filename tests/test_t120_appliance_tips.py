"""T1.20 — appliance tips / thresholds na /forecast/hourly."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pandas as pd

from api.services.forecast_ml import get_hourly_forecast


def test_hourly_forecast_includes_appliance_tips_and_thresholds(monkeypatch):
    day = (date.today().fromordinal(date.today().toordinal() + 1)).isoformat()
    frame = pd.DataFrame(
        {
            'day': [day] * 5,
            'hour': [10, 11, 12, 13, 14],
            'predicted_kwh': [3.5, 4.0, 2.5, 1.8, 0.4],
            'prediction_source': ['model'] * 5,
        }
    )
    predictor = MagicMock()
    predictor.predict_days.return_value = frame
    predictor.model_path = 'models/pv_hourly_model.joblib'

    monkeypatch.setattr(
        'src.models.forecast_validation.get_actual_hourly_ml',
        lambda *a, **k: pd.DataFrame(columns=['hour', 'actual_pv_ml_kwh']),
    )

    out = get_hourly_forecast(predictor, day)
    assert out['total_kwh'] == 12.2
    assert len(out['appliance_thresholds']) == 4
    labels = {t['label'] for t in out['appliance_thresholds']}
    assert 'Pralka' in labels and 'Zmywarka' in labels
    assert len(out['appliance_tips']) == 5
    top = out['appliance_tips'][0]
    assert top['rank'] == 1
    assert top['hour'] == 11
    assert 'Suszarka' in top['appliances']  # 4.0 >= 2.0
