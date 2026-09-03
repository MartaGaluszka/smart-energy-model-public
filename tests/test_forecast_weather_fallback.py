"""Gdy ENSEMBLE_PRIMARY=1, dni sprzed ensemble (≤26.08) biorą ICON, nie padają na 422."""

from __future__ import annotations

import sqlite3

import pandas as pd

from src.models.pv_hourly_predictor import (
    _coalesce_hourly_weather,
    load_forecast_weather_hourly,
)


def _make_db(path: str, rows: list[tuple[str, str, float]]) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        '''
        CREATE TABLE weather_data (
            timestamp DATETIME,
            temperature_celsius REAL,
            humidity_percent REAL,
            cloud_cover_percent REAL,
            cloud_cover_low_percent REAL,
            cloud_cover_mid_percent REAL,
            solar_radiation_wm2 REAL,
            wind_speed_ms REAL,
            visibility_m REAL,
            snow_depth_m REAL,
            precipitation_mm REAL,
            location TEXT,
            data_source TEXT
        )
        '''
    )
    conn.executemany(
        '''
        INSERT INTO weather_data (
            timestamp, solar_radiation_wm2, cloud_cover_percent, data_source
        ) VALUES (?, ?, 40, ?)
        ''',
        rows,
    )
    conn.commit()
    conn.close()


def test_ensemble_primary_falls_back_to_icon_before_gate(tmp_path, monkeypatch):
    monkeypatch.setenv('ENSEMBLE_PRIMARY', '1')
    monkeypatch.delenv('WEATHER_FORECAST_SOURCE_LIKE', raising=False)
    db = str(tmp_path / 'w.db')
    _make_db(
        db,
        [
            ('2026-08-26 12:00:00', 500.0, 'OpenMeteo-forecast'),
            ('2026-08-27 12:00:00', 600.0, 'OpenMeteo-forecast'),
            ('2026-08-27 12:00:00', 610.0, 'OpenMeteo-forecast-ensemble-icon_seamless+ukmo_seamless'),
        ],
    )

    pre = load_forecast_weather_hourly(db, '2026-08-26', '2026-08-26')
    assert not pre.empty
    assert float(pre.loc[pre['hour'] == 12, 'radiation_wm2'].iloc[0]) == 500.0

    gate = load_forecast_weather_hourly(db, '2026-08-27', '2026-08-27')
    assert float(gate.loc[gate['hour'] == 12, 'radiation_wm2'].iloc[0]) == 610.0


def test_coalesce_fills_missing_ensemble_hours():
    primary = pd.DataFrame({'day': ['2026-08-27'], 'hour': [12], 'radiation_wm2': [610.0]})
    fallback = pd.DataFrame(
        {
            'day': ['2026-08-27', '2026-08-27'],
            'hour': [10, 12],
            'radiation_wm2': [400.0, 600.0],
        }
    )
    out = _coalesce_hourly_weather(primary, fallback)
    by_hour = {int(r.hour): float(r.radiation_wm2) for r in out.itertuples(index=False)}
    assert by_hour[10] == 400.0
    assert by_hour[12] == 610.0


def test_past_day_chart_prefers_full_daily_archive(monkeypatch):
    from unittest.mock import MagicMock

    from api.services.forecast_ml import get_hourly_forecast

    day = '2026-08-27'
    daily = pd.DataFrame(
        {
            'day': [day] * 14,
            'hour': list(range(6, 20)),
            'predicted_kwh': [2.0] * 14,
            'prediction_source': ['model'] * 14,
        }
    )
    midday = pd.DataFrame(
        {
            'day': [day] * 8,
            'hour': list(range(12, 20)),
            'predicted_kwh': [3.0] * 8,
            'prediction_source': ['model'] * 8,
        }
    )

    def fake_snapshot(label, target):
        if target != day:
            return pd.DataFrame(), None
        if label == 'daily':
            return daily, None
        if label == 'midday':
            return midday, None
        return pd.DataFrame(), None

    monkeypatch.setattr('src.models.forecast_validation.load_forecast_snapshot', fake_snapshot)
    monkeypatch.setattr(
        'src.models.forecast_validation.get_actual_hourly_ml',
        lambda *a, **k: pd.DataFrame(columns=['hour', 'actual_pv_ml_kwh']),
    )
    predictor = MagicMock()
    out = get_hourly_forecast(predictor, day)
    predictor.predict_days.assert_not_called()
    hours = [h['hour'] for h in out['hours']]
    assert hours == list(range(6, 20))
    assert out['total_kwh'] == 28.0
    primary = pd.DataFrame({'day': ['2026-08-27'], 'hour': [12], 'radiation_wm2': [610.0]})
    fallback = pd.DataFrame(
        {
            'day': ['2026-08-27', '2026-08-27'],
            'hour': [10, 12],
            'radiation_wm2': [400.0, 600.0],
        }
    )
    out = _coalesce_hourly_weather(primary, fallback)
    by_hour = {int(r.hour): float(r.radiation_wm2) for r in out.itertuples(index=False)}
    assert by_hour[10] == 400.0
    assert by_hour[12] == 610.0
